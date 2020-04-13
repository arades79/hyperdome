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
import hmac
from . import models
import os
import queue
import socket
from urllib.request import urlopen
import traceback
import json
import secrets
import logging
import base64
from .app import app, db
from flask import request, render_template, abort, make_response


class Web(object):
    """
    The Web object is the OnionShare web server, powered by flask
    """

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

    def __init__(self, common, is_gui):
        self.common = common
        self.common.log("Web", "__init__", f"is_gui={is_gui}")
        app.secret_key = self.common.random_string(8)

        # Debug mode?
        if self.common.debug:
            self.debug_mode()

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
        self.slug = None
        self.error404_count = 0

        self.done = False

        # shutting down the server only works within the context of flask, so
        # the easiest way to do it is over http
        self.shutdown_slug = self.common.random_string(16)

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
        self.info = {
            "name": "hyperdome",
            "version": self.common.version,
            "online": str(len(self.counselors_available)),
        }

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
            e_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            print(e_str)
            return "Exception raised", 500

        @app.route("/probe")
        def probe():
            self.info["online"] = str(len(self.counselors_available))
            return json.dumps(self.info)

        @app.route("/request_counselor", methods=["POST"])
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

        @app.route("/poll_connected_guest", methods=["GET"])
        def poll_connected_guest():
            counselor_id = request.form["counselor_id"]
            guest_key = self.guest_keys.pop(counselor_id, "")
            return guest_key

        @app.route("/counseling_complete", methods=["POST"])
        def counseling_complete():
            sid = request.form["user_id"]
            if sid not in self.active_chat_user_map:
                return "no active chat", 404
            other_user = self.active_chat_user_map[sid]
            self.active_chat_user_map.pop(sid)
            self.pending_messages.pop(sid, "")
            self.active_chat_user_map.update({other_user: ""})
            if sid in self.counselors_available:
                counselor_id = sid
            elif other_user in self.counselors_available:
                counselor_id = other_user
            else:
                return "Counselor has left the chat"
            self.counselors_available[counselor_id] += 1
            return "Chat Ended"

        @app.route("/counselor_signout", methods=["POST"])
        def counselor_signout():
            sid = request.form["user_id"]
            self.counselors_available.pop(sid, "")
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
                return "Bad signature", 401
            sid = self.common.random_string(16)
            # will use capacity variable for this later
            self.counselors_available[sid] = 1
            self.counselor_keys[sid] = session_counselor_key
            return sid

        @app.route("/counselor_signup", methods=["POST"])
        def counselor_signup():
            username = request.form["username"]
            counselor_key = request.form["pub_key"]
            signup_code = request.form["signup_code"]
            signature = request.form["signature"]
            signature = base64.urlsafe_b64decode(signature)
            activator = models.CounselorSignUp.query.filter_by(passphrase=signup_code).first_or_404()
            db.session.delete(activator)
            counselor = models.Counselor(name=username, key_bytes=counselor_key)
            if  counselor.verify(signature, signup_code):
                models.db.session.add(counselor)
                models.db.session.commit()
                return "Good"  # TODO: add better responses
            else:
                models.db.session.commit()
                return "User not Registered", 400

        @app.route("/generate_guest_id")
        def generate_guest_id():
            # TODO check for collisions
            return self.common.random_string(16)

        @app.route("/send_message", methods=["POST"])
        def message_from_user():
            message = request.form["message"]
            user_id = request.form["user_id"]
            if user_id not in self.active_chat_user_map:
                return "no chat", 404
            other_user = self.active_chat_user_map[user_id]
            if other_user in self.pending_messages:
                self.pending_messages[other_user] += f"\n{message}"
            elif other_user:  # may be empty string if other disconnected
                self.pending_messages[other_user] = message
            else:
                return "user left", 404
            return "Success"

        @app.route("/chat_status")
        def chat_status():
            user_id = request.form["user_id"]
            try:
                return (
                    "CHAT_OVER"
                    if self.active_chat_user_map[user_id] == ""
                    else "CHAT_ACTIVE"
                )
            except KeyError:
                return "NO_CHAT"

        @app.route("/collect_messages", methods=["GET"])
        def collect_messages():
            guest_id = request.form["user_id"]
            return self.pending_messages.pop(guest_id, "")

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

    def generate_slug(self, persistent_slug=None):
        self.common.log(
            "Web", "generate_slug", "persistent_slug={}".format(persistent_slug)
        )
        if persistent_slug is not None and persistent_slug != "":
            self.slug = persistent_slug
            self.common.log(
                "Web",
                "generate_slug",
                'persistent_slug sent, so slug is: "{}"'.format(self.slug),
            )
        else:
            self.slug = self.common.build_slug()
            self.common.log(
                "Web", "generate_slug", 'built random slug: "{}"'.format(self.slug)
            )

    def debug_mode(self):
        """
        Turn on debugging mode, which will log flask errors to a debug file.
        """
        flask_debug_filename = os.path.join(
            self.common.build_data_dir(), "flask_debug.log"
        )
        log_handler = logging.FileHandler(flask_debug_filename)
        log_handler.setLevel(logging.WARNING)
        app.logger.addHandler(log_handler)

    def check_shutdown_slug_candidate(self, slug_candidate):
        self.common.log(
            "Web",
            "check_shutdown_slug_candidate: slug_candidate="
            "{}".format(slug_candidate),
        )
        if not hmac.compare_digest(self.shutdown_slug, slug_candidate):
            abort(404)

    def force_shutdown(self):
        """
        Stop the flask web server, from the context of the flask app.
        """
        # Shutdown the flask service
        func = request.environ.get("werkzeug.server.shutdown")
        if func is None:
            raise RuntimeError("Not running with the Werkzeug Server")
        func()
        self.running = False

    def start(self, port, stay_open=False):
        """
        Start the flask web server.
        """
        self.common.log("Web", "start", f"port={port}, stay_open={stay_open}")

        self.stay_open = stay_open

        # Make sure the stop_q is empty when starting a new server
        while not self.stop_q.empty():
            try:
                self.stop_q.get(block=False)
            except queue.Empty:
                pass

        # In Whonix, listen on 0.0.0.0 instead of 127.0.0.1 (#220)
        host = (
            "0.0.0.0"
            if os.path.exists("/usr/share/anon-ws-base-files/workstation")
            else "127.0.0.1"
        )

        self.running = True
        app.run(host=host, port=port, threaded=True)

    def stop(self, port):
        """
        Stop the flask web server by loading /shutdown.
        """
        self.common.log("Web", "stop", "stopping server")

        # Let the mode know that the user stopped the server
        self.stop_q.put(True)

        # Reset any slug that was in use
        self.slug = ""

        # To stop flask, load http://127.0.0.1:<port>/<shutdown_slug>/shutdown
        if self.running:
            try:
                s = socket.socket()
                s.connect(("127.0.0.1", port))
                s.sendall(
                    "GET /{0:s}/shutdown HTTP/1.1\r\n\r\n".format(self.shutdown_slug).encode()
                )
            except TypeError:
                try:
                    urlopen(
                        "http://127.0.0.1:{0:d}/{1:s}/shutdown".format(
                            port, self.shutdown_slug
                        )
                    ).read()
                except TypeError:
                    pass
