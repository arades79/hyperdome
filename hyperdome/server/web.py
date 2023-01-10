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
from queue import Queue
import secrets
import socket
from time import sleep
from urllib.request import urlopen
from threading import Lock

import autologging
from flask import abort, jsonify, make_response, render_template, request

from . import models
from ..common.common import version, data_path, resource_path
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

    lock = Lock()

    def __init__(self):

        db_uri = f"sqlite:///{data_path / 'hyperdome_server.db'}"
        app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
        self.__log.debug(f"{db_uri=}")
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        db.init_app(app)

        app.secret_key = secrets.token_urlsafe(8)

        with app.app_context():
            db.create_all()

        # If the user stops the server while a transfer is in progress, it
        # should immediately stop the transfer. In order to make it
        # thread-safe, stop_q is a queue. If anything is in it,
        # then the user stopped the server.
        self.stop_q = Queue()

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

        self.q = Queue()
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
        self.counselors_available: set[str] = set()
        # self.active_chat_user_map = dict()
        self.active_chats: dict[str, Queue[str]] = dict()
        self.guest_keys = {}
        self.counselor_keys = {}
        self.active_codes = set()

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
            return "Exception raised", 500

        @app.route("/probe")
        def probe():
            return jsonify(
                name="hyperdome",
                version=version,
                online=len(self.counselors_available),
            )

        @app.route("/request_counselor", methods=["POST"])
        def request_counselor():
            guest_id = request.form["guest_id"]
            guest_key = request.form["pub_key"]
            if not self.counselors_available:
                return ""
            with Web.lock:
                chosen_counselor = secrets.choice(tuple(self.counselors_available))
                self.counselors_available.remove(chosen_counselor)
            self.active_chats[guest_key] = Queue()
            self.guest_keys[chosen_counselor] = guest_key
            counselor_key = self.counselor_keys.pop(chosen_counselor)
            self.active_chats[counselor_key] = Queue()
            return counselor_key

        @app.route("/poll_connected_guest", methods=["GET"])
        def poll_connected_guest():
            counselor_id = request.form["counselor_id"]
            guest_key = self.guest_keys.pop(counselor_id, "")
            return guest_key

        @app.route("/counseling_complete", methods=["POST"])
        def counseling_complete():
            sid = request.form["user_id"]
            if sid not in self.active_chats.keys():
                return "no active chat", 404
            with Web.lock:
                self.active_chats.pop(sid)
            return "Chat Ended"

        @app.route("/counselor_signout", methods=["POST"])
        def counselor_signout():
            sid = request.form["user_id"]
            with Web.lock:
                self.counselors_available.remove(sid)
                self.counselor_keys.pop(sid, "")
            return "Success"

        @app.route("/counselor_signin", methods=["POST"])
        def counselor_signin():
            username = request.form["username"]
            session_counselor_key = request.form["pub_key"]
            signature = request.form["signature"]
            signature = base64.urlsafe_b64decode(signature)
            counselor = models.Counselor.query.filter_by(name=username).first_or_404()
            if not counselor.verify(signature, session_counselor_key):
                self.__log.info(
                    f"attempted counselor login failed verification {username=}"
                )
                return "Bad signature", 401
            sid = secrets.token_urlsafe(16)
            # will use capacity variable for this later
            self.counselors_available.add(sid)
            self.counselor_keys[sid] = session_counselor_key
            self.__log.info(f"successful counselor login {username=}")
            return sid

        @app.route("/counselor_signup", methods=["POST"])
        def counselor_signup():
            username = request.form["username"]
            counselor_key = request.form["pub_key"]
            signup_code = request.form["signup_code"]
            signature = request.form["signature"]
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

                return "Good"  # TODO: add better responses
            else:
                models.db.session.commit()
                self.__log.warning(
                    f"{username=} attempted registration but failed key verification"
                )
                return "User not Registered", 400

        @app.route("/generate_guest_id")
        def generate_guest_id():
            # TODO check for collisions
            return secrets.token_urlsafe(16)

        @app.route("/send_message", methods=["POST"])
        def message_from_user():
            message = request.form["message"]
            user_id = request.form["user_id"]
            try:
                self.active_chats[user_id].put_nowait(message)
            except KeyError:
                return "no chat", 404
            return "Success"

        @app.route("/collect_messages", methods=["GET"])
        def collect_messages():
            user_id = request.form["user_id"]
            messages: str = ""
            try:
                message_queue = self.active_chats[user_id]
                while not message_queue.empty():
                    messages += f"{message_queue.get_nowait()}\n"
                chat_status = "CHAT_ACTIVE"
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

    def start(self, host: str, port: int, stay_open: bool = False):
        """
        Start the flask web server.
        """
        self.stay_open = stay_open
        app.run(host=host, port=port, threaded=True)
        self.running = True

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


def check_stop(web: Web):
    # Make sure the stop_q is empty when starting a new server
    while not web.stop_q.empty():
        try:
            web.stop_q.get(block=False)
            web.__log.debug("startup waiting for queue to be empty...")
            sleep(0.1)
        except queue.Empty:
            pass
