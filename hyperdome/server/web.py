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
        self.counselors_available = {}
        self.active_chat_user_map = {}
        self.pending_messages = {}
        self.guest_keys = {}
        self.counselor_keys = {}
        self.active_codes = []

        #

    def define_common_routes(self):
        """
        Common web app routes between sending and receiving
        """

        @app.errorhandler(404)
        def page_not_found(e):
            """
            404 error page.
            """
            return self.error404()

        @app.route("/<slug_candidate>/shutdown")
        def shutdown(slug_candidate):
            """
            Stop the flask web server, from the context of an http request.
            """
            self.check_shutdown_slug_candidate(slug_candidate)
            self.force_shutdown()
            return ""

        @app.route("/noscript-xss-instructions")
        def noscript_xss_instructions():
            """
            Display instructions for disabling Tor Browser's
            NoScript XSS setting
            """
            r = make_response(render_template("receive_noscript_xss.html"))
            return self.add_security_headers(r)

        @app.errorhandler(Exception)
        def unhandled_exception(e):
            self.__log.exception("server request exception")
            return jsonify(error="Unhandled exception during request"), 500

        @app.route("/hyperdome/info")
        def info():
            return jsonify(
                name="hyperdome",  # TODO: admin configuable name that's set as nick in client
                version=version,
                api=["v1"],
                base_url="/hyperdome/api/",
                online=len(self.counselors_available),
            )

        @app.route("/hyperdome/api/v1/counselor", "counselor", methods=["GET"])
        def request_counselor():
            guest_id = request.form["guest_id"]
            guest_key = request.form["pub_key"]
            counselors = [
                counselor
                for counselor, capacity in self.counselors_available.items()
                if capacity
            ]
            if not counselors:
                return ""
            chosen_counselor = secrets.choice(counselors)
            self.counselors_available[chosen_counselor] -= 1
            self.active_chat_user_map[guest_id] = chosen_counselor
            self.active_chat_user_map[chosen_counselor] = guest_id
            self.guest_keys[chosen_counselor] = guest_key
            counselor_key = self.counselor_keys.pop(chosen_counselor)
            return counselor_key

        @app.route("/hyperdome/api/v1/guest/<counselor_id>", "guest", methods=["GET"])
        def poll_connected_guest(counselor_id):
            guest_key = self.guest_keys.pop(counselor_id, "")
            return jsonify(guest_key=guest_key)

        @app.route(
            "/hyperdome/api/v1/messages/<user_id>", "messages", methods=["DELETE"]
        )
        def counseling_complete(user_id):
            if user_id not in self.active_chat_user_map:
                return jsonify(error="no active chat"), 404
            other_user = self.active_chat_user_map[user_id]
            self.active_chat_user_map.pop(user_id)
            self.pending_messages.pop(user_id, "")
            try:
                self.active_chat_user_map[other_user] = ""
            except KeyError:
                self.__log.debug("other user already left chat")
                pass
            finally:
                return jsonify(message="chat ended"), 200

        @app.route("/hyperdome/api/v1/counselor/", "counselor")
        @app.route(
            "/hyperdome/api/v1/counselor/<counselor_id>", "counselor", methods=["PUT"]
        )
        def counselor_login(counselor_id=None):
            if counselor_id is not None:
                self.counselors_available.pop(counselor_id, "")
                self.counselor_keys.pop(counselor_id, "")
                self.__log.info("counselor logged out")
                return jsonify(message="Successful logout"), 200
            else:
                username = request.json["username"]
                session_counselor_key = request.json["pub_key"]
                signature = request.json["signature"]
                signature = base64.urlsafe_b64decode(signature)
                counselor = models.Counselor.query.filter_by(
                    name=username
                ).first_or_404()
                if not counselor.verify(signature, session_counselor_key):
                    self.__log.warning(
                        f"attempted counselor login failed verification {username=}"
                    )
                    return "Bad signature", 403
                sid = secrets.token_urlsafe(16)
                # will use capacity variable for this later
                self.counselors_available[sid] = 1
                self.counselor_keys[sid] = session_counselor_key
                self.__log.info(f"successful counselor login {username=}")
                return jsonify(user_id=sid), 200

        @app.route("/hyperdome/api/v1/counselor/", "counselor", methods=["POST"])
        def counselor_signup():
            username = request.json["username"]
            counselor_key = request.json["pub_key"]
            signup_code = request.json["signup_code"]
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

        @app.route("/hyperdome/api/v1/guest", "guest", methods=["POST"])
        def generate_guest_id():
            # TODO check for collisions
            return jsonify(user_id=secrets.token_urlsafe(16)), 201

        @app.route("/hyperdome/api/v1/messages/<user_id>", "messages", methods=["PUT"])
        def message_from_user(user_id):
            if user_id not in self.active_chat_user_map:
                return jsonify(error="no chat"), 404
            messages: list = request.json["messages"]
            other_user = self.active_chat_user_map[user_id]
            if other_user in self.pending_messages:
                self.pending_messages[other_user] += messages
            elif other_user:  # may be empty string if other disconnected
                self.pending_messages[other_user] = messages
            else:
                return jsonify(error="user left"), 404
            return jsonify(message="Success")

        @app.route("/hyperdome/api/v1/messages/<user_id>", methods=["GET"])
        def collect_messages(user_id):
            messages = self.pending_messages.pop(user_id, "")
            try:
                chat_status = (
                    "CHAT_OVER"
                    if self.active_chat_user_map[user_id] == ""
                    else "CHAT_ACTIVE"
                )
            except KeyError:
                chat_status = "NO_CHAT"
            return jsonify(chat_status=chat_status, messages=messages)

    def error404(self):
        self.add_request(Web.REQUEST_OTHER, request.path)
        if request.path != "/favicon.ico":
            self.error404_count += 1

            # In receive mode, with public mode enabled, skip rate limiting
            # 404s
            if self.error404_count == 20:
                self.add_request(Web.REQUEST_RATE_LIMIT, request.path)
                self.force_shutdown()

        r = make_response(render_template("404.html"), 404)
        return self.add_security_headers(r)

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
