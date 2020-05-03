# -*- coding: utf-8 -*-
"""
Hyperdome

Copyright (C) 2019 Skyelar Craver <scravers@protonmail.com>
                   and Steven Pitts <makusu2@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import base64
import hmac
from pathlib import Path
import queue
import secrets
import socket
from time import sleep
from urllib.request import urlopen

import autologging
from flask import abort, jsonify, make_response, render_template, request

from . import models
from ..common.common import version
from .app import app, db


@autologging.traced
@autologging.logged
class Web:
    """
    The Web object is the hyperdome web server, powered by flask
    """

    __log: autologging.logging.Logger  # makes linter happy about autologging

    REQUEST_LOAD = 0
    REQUEST_STARTED = 1
    REQUEST_PROGRESS = 2
    REQUEST_OTHER = 3
    REQUEST_CANCELED = 4
    REQUEST_RATE_LIMIT = 5
    REQUEST_UPLOAD_FILE_RENAMED = 6
    REQUEST_UPLOAD_SET_DIR = 7
    REQUEST_UPLOAD_FINISHED = 8
    REQUEST_UPLOAD_CANCELED = 9
    REQUEST_ERROR_DATA_DIR_CANNOT_CREATE = 10

    def __init__(self):
        app.secret_key = secrets.token_urlsafe(8)

        # If the user stops the server while a transfer is in progress, it
        # should immediately stop the transfer. In order to make it
        # thread-safe, stop_q is a queue. If anything is in it,
        # then the user stopped the server.
        self.stop_q = queue.Queue()

        self.security_headers = [
            (
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self'; "
                "script-src 'self'; img-src 'self' data:;",
            ),
            ("X-Frame-Options", "DENY"),
            ("X-Xss-Protection", "1; mode=block"),
            ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer"),
            ("Server", "Hyperdome"),
        ]

        self.q = queue.Queue()
        self.error404_count = 0

        self.done = False

        # shutting down the server only works within the context of flask, so
        # the easiest way to do it is over http
        self.shutdown_slug = secrets.token_urlsafe(16)

        # Keep track if the server is running
        self.running = False

        # Define the web app routes
        self.define_common_routes()

        # hyperdome server user tracking variables
        self.counselors = {}
        self.guests = {}
        self.chats = {}

        #

    def define_common_routes(self):
        """
        Common web app routes between sending and receiving
        """

        @app.errorhandler(404)
        def page_not_found(message=""):
            """
            404 error message.
            """
            return jsonify(error=message), 404

        @app.route("/<string:slug_candidate>/shutdown")
        def shutdown(slug_candidate):
            """
            Stop the flask web server, from the context of an http request.
            """
            self.check_shutdown_slug_candidate(slug_candidate)
            self.force_shutdown()
            return ""

        @app.errorhandler(Exception)
        def unhandled_exception(e):
            self.__log.exception("server request exception")
            return jsonify(error="Unhandled server error during request"), 500

        @app.route("/hyperdome/api")
        def api():
            return jsonify(
                name="hyperdome",  # TODO: admin configuable name that's set as nick in client
                version=version,
                api=["v1"],
            )

        @app.route("/hyperdome/api/v1/counselors/<string:guest_id>", methods=["GET"])
        def request_counselor(guest_id):
            if guest_id not in self.guests:
                abort(404, message="guest data not found")
            counselors = [
                counselor
                for counselor in self.counselors
                if not (
                    counselor in self.chats or counselor.get("connected_guest", None)
                )
            ]
            if not counselors:
                return jsonify(error="no counselors available")
                # TODO: implement guest queue
            counselor_id = secrets.choice(counselors)
            self.counselors[counselor_id]["connected_guest"] = guest_id
            return jsonify(counselor=self.counselors[counselor_id])

        @app.route("/hyperdome/api/v1/guests/<string:counselor_id>", methods=["GET"])
        def poll_connected_guest(counselor_id):
            try:
                guest_id = self.counselors[counselor_id]["connected_guest"]
                guest = self.guests[guest_id]
            except KeyError:
                abort(404, message="Connected guest not found")
            else:
                return jsonify(guest=guest)

        @app.route("/hyperdome/api/v1/counselors/", methods=["POST"])
        def counselor_login():
            username = request.json["username"]
            session_counselor_key = request.json["pub_key"]
            signature = request.json["signature"]
            signature = base64.urlsafe_b64decode(signature)
            counselor = models.Counselor.query.filter_by(name=username).first_or_404()
            if not counselor.verify(signature, session_counselor_key):
                self.__log.warning(
                    f"attempted counselor login failed verification {username=}"
                )
                request
                return jsonify(error="Bad signature"), 403
            sid = secrets.token_urlsafe(16)
            # will use capacity variable for this later
            self.counselors[sid] = {
                "username": username,
                "public_key": counselor.key_bytes,
                "session_key": session_counselor_key,
            }
            self.__log.info(f"successful counselor login {username=}")
            return jsonify(user_id=sid), 201

        # TODO: memoize
        @app.route("/hyperdome/api/v1/counselors/", methods=["GET"])
        def get_counselor_keys():
            keys = models.Counselor.query.add_columns(models.Counselor.key_bytes).all()
            return jsonify(counselor_pub_keys=keys)

        @app.route(
            "/hyperdome/api/v1/counselors/<string:counselor_id>",
            methods=["PUT", "DELETE"],
        )
        def counselor_logout(counselor_id=None):
            if counselor_id is not None:
                self.counselors.pop(counselor_id, "")
                self.chats.pop(counselor_id, "")
                self.__log.info("counselor logged out")
                return jsonify(message="Successful logout"), 200

        @app.route(
            "/hyperdome/api/v1/counselors/<string:signup_code>", methods=["POST"]
        )
        def counselor_signup(signup_code):
            username = request.json["username"]
            counselor_key = request.json["pub_key"]
            signature = request.json["signature"]
            signature = base64.urlsafe_b64decode(signature)
            activator = models.CounselorSignUp.query.filter_by(
                passphrase=signup_code
            ).first_or_404()
            db.session.delete(activator)
            counselor = models.Counselor(name=username, key_bytes=counselor_key)
            if counselor.verify(signature, signup_code):
                models.db.session.add(counselor)
                models.db.session.commit()
                self.__log.info(f"new counselor {username=} added")

                return jsonify(message=f"successfully signed up as {username}"), 201
            else:
                models.db.session.commit()
                self.__log.warning(
                    f"{username=} attempted registration but failed key verification"
                )
                return (
                    jsonify(error="invalid signature in signup,"),
                    403,
                )

        @app.route("/hyperdome/api/v1/guests", methods=["POST"])
        def generate_guest_id():
            sid = self.get_unique_sid()
            key = request.json["pub_key"]
            sig = request.json["signature"]
            # TODO: Verify signature
            self.guests[sid] = {"pub_key": key}
            return jsonify(user_id=sid), 201

        @app.route("/hyperdome/api/v1/chats/<string:user_id>", methods=["POST"])
        def start_chat(user_id):
            self.chats[user_id] = {
                "key_data": request.json["key_data"],
                "signature": request.json["signature"],
                "messages": [],
                "sequence": 0,
            }

        @app.route("/hyperdome/api/v1/chats/<string:user_id>", methods=["GET"])
        def get_key_data(user_id):
            try:
                if user_id in self.counselors:
                    partner_id = self.counselors[user_id]["connected_guest"]
                elif user_id in self.guests:
                    partner_id = self.guests[user_id]["connected_counselor"]
                else:
                    abort(404, message="no user found for user id")
                    return
            except KeyError:
                abort(404, message="user has no chat partner")
                return
            try:
                chat = self.chats[partner_id]
                key_data = chat["key_data"]
                signature = chat["signature"]
            except:
                abort(404, message="partner has not yet initialized chat")
                return
            else:
                return jsonify(key_data=key_data, signature=signature)

        @app.route(
            "/hyperdome/api/v1/chats/<string:user_id>/<int:message_no>/",
            methods=["POST"],
        )
        def message_from_user(user_id, message_no):
            messages: list = request.json["messages"]
            try:
                chat_partner = self.chats[user_id]["partner"]
                self.chats[chat_partner]["messages"] += messages
                self.chats[chat_partner]["sequence"] = message_no
            except KeyError:
                abort(404, message="couldn't find message destination")
            return jsonify(message="Success", no_messages=len(messages))

        @app.route(
            "/hyperdome/api/v1/chats/<string:user_id>/<int:message_no>/",
            methods=["GET"],
        )
        def collect_messages(user_id, message_no):
            try:
                messages = self.chats[user_id]["messages"][message_no:]
                no_messages = len(messages)
                next_message = message_no + no_messages
            except KeyError:
                abort(404, message="no chat")
                return  # should be inaccessible
            except IndexError:
                messages = []
                no_messages = 0
                next_message = message_no
                pass
            return jsonify(
                no_messages=no_messages,
                messages=messages,
                next_message=next_message,
                sequence=self.chats[user_id]["sequence"],
            )

        @app.route(
            "/hyperdome/api/v1/chats/<string:user_id>/<int:message_no>/",
            methods=["DELETE"],
        )
        def clear_read_messages(user_id, message_no):
            try:
                messages = self.chats[user_id]["messages"]
                self.chats[user_id]["messages"] = messages[message_no:]
            except KeyError:
                abort(404, message="no chat")
            except IndexError:
                self.chats[user_id]["messages"] = []
                pass
            return jsonify(message="Success", next_message=0)

        @app.route("/hyperdome/api/v1/chats/<string:user_id>/", methods=["DELETE"])
        def counseling_complete(user_id):
            try:
                self.chats.pop(user_id)
            except KeyError:
                abort(404, message="No chat found for user id")
            if user_id in self.guests:
                self.guests[user_id].pop("connected_counselor")
            elif user_id in self.counselors:
                self.counselors[user_id].pop("connected_guest")
            return jsonify(message="chat ended")

    def get_unique_sid(self):
        sid_candidates = [secrets.token_urlsafe(20) for i in range(5)]
        unique_sids = [
            sid
            for sid in sid_candidates
            if not (sid in self.counselors or sid in self.guests or sid in self.chats)
        ]
        sid = secrets.choice(unique_sids)
        return sid

    def error403(self):
        self.add_request(Web.REQUEST_OTHER, request.path)

        r = make_response(render_template("403.html"), 403)
        return self.add_security_headers(r)

    def add_security_headers(self, r):
        """
        Add security headers to a request
        """
        for header, value in self.security_headers:
            r.headers.set(header, value)
        return r

    def _safe_select_jinja_autoescape(self, filename):
        return filename is None or filename.endswith(
            (".html", ".htm", ".xml", ".xhtml")
        )

    def add_request(self, request_type, path, data=None):
        """
        Add a request to the queue, to communicate with the GUI.
        """
        self.q.put({"type": request_type, "path": path, "data": data})

    def check_shutdown_slug_candidate(self, slug_candidate):
        if not hmac.compare_digest(self.shutdown_slug, slug_candidate):
            self.__log.warning("slug failed verification")
            abort(404)

    def force_shutdown(self):
        """
        Stop the flask web server, from the context of the flask app.
        """
        # Shutdown the flask service
        func = request.environ.get("werkzeug.server.shutdown")
        if func is None:
            err = "Not running with the Werkzeug Server"
            self.__log.error(err)
            raise RuntimeError(err)
        func()
        self.running = False

    def start(self, port, stay_open=False):
        """
        Start the flask web server.
        """

        self.stay_open = stay_open

        # Make sure the stop_q is empty when starting a new server
        while not self.stop_q.empty():
            try:
                self.stop_q.get(block=False)
                self.__log.debug("startup waiting for queue to be empty...")
                sleep(0.1)
            except queue.Empty:
                pass

        # In Whonix, listen on 0.0.0.0 instead of 127.0.0.1 (#220)
        host = (
            "0.0.0.0"
            if Path("/usr/share/anon-ws-base-files/workstation").exists()
            else "127.0.0.1"
        )

        self.running = True
        app.run(host=host, port=port, threaded=True)

    def stop(self, port):
        """
        Stop the flask web server by loading /shutdown.
        """
        self.__log.info("stopping server")

        # Let the mode know that the user stopped the server
        self.stop_q.put(True)

        # To stop flask, load http://127.0.0.1:<port>/<shutdown_slug>/shutdown
        if self.running:
            try:
                s = socket.socket()
                s.connect(("127.0.0.1", port))
                s.sendall(
                    f"GET /{self.shutdown_slug:s}/shutdown HTTP/1.1\r\n\r\n".encode()
                )
            except TypeError:
                self.__log.info("couldn't shutdown from socket, trying urlopen")
                try:
                    urlopen(
                        f"http://127.0.0.1:{port:d}/{self.shutdown_slug:s}/shutdown"
                    ).read()
                except TypeError:
                    self.__log.warning("shutdown url failed", exc_info=True)
                    pass
