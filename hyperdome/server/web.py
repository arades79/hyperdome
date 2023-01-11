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
from fastapi import HTTPException, FastAPI, Form

import uvicorn

from . import models
from ..common.common import version, data_path, resource_path

app = FastAPI()


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

        @app.get("/probe")
        def probe():
            return {
                "name": "hyperdome",
                "version": version,
                "online": len(self.counselors_available),
            }

        @app.post("/request_counselor")
        def request_counselor(guest_id: str = Form(), guest_key: str = Form()):
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

        @app.get("/poll_connected_guest")
        def poll_connected_guest(counselor_id: str = Form()):
            guest_key = self.guest_keys.pop(counselor_id, "")
            return guest_key

        @app.post("/counseling_complete")
        def counseling_complete(user_id: str = Form()):
            if user_id not in self.active_chats.keys():
                raise HTTPException(404, "no active chat")
            with Web.lock:
                self.active_chats.pop(user_id)
            return "Chat Ended"

        @app.post("/counselor_signout")
        def counselor_signout(user_id: str = Form()):
            with Web.lock:
                self.counselors_available.remove(user_id)
                self.counselor_keys.pop(user_id, "")
            return "Success"

        @app.post("/counselor_signin")
        def counselor_signin(
            username: str = Form(),
            pub_key: str = Form(),
            signature: str | bytes = Form(),
        ):
            signature = base64.urlsafe_b64decode(signature)
            counselor = models.Counselor.query.filter_by(name=username).first_or_404()
            if not counselor.verify(signature, pub_key):
                self.__log.info(
                    f"attempted counselor login failed verification {username=}"
                )
                raise HTTPException(401, "Bad signature")
            sid = secrets.token_urlsafe(16)
            # will use capacity variable for this later
            self.counselors_available.add(sid)
            self.counselor_keys[sid] = pub_key
            self.__log.info(f"successful counselor login {username=}")
            return sid

        @app.post("/counselor_signup")
        def counselor_signup(
            username: str = Form(),
            pub_key: str = Form(),
            signup_code: str = Form(),
            signature: str | bytes = Form(),
        ):
            signature = base64.urlsafe_b64decode(signature)
            activator = models.CounselorSignUp.query.filter_by(
                passphrase=signup_code
            ).first_or_404()
            db.session.delete(activator)
            counselor = models.Counselor(name=username, key_bytes=pub_key)
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
                raise HTTPException(400, "User not Registered")

        @app.get("/generate_guest_id")
        def generate_guest_id():
            # TODO check for collisions
            return secrets.token_urlsafe(16)

        @app.post("/send_message")
        def message_from_user(message: str = Form(), user_id: str = Form()):
            try:
                self.active_chats[user_id].put_nowait(message)
            except KeyError:
                raise HTTPException(404, "no chat")
            return "Success"

        @app.get("/collect_messages")
        def collect_messages(user_id: str = Form()):
            messages: str = ""
            try:
                message_queue = self.active_chats[user_id]
                while not message_queue.empty():
                    messages += f"{message_queue.get_nowait()}\n"
                chat_status = "CHAT_ACTIVE"
            except KeyError:
                chat_status = "NO_CHAT"
            return {"chat_status": chat_status, "messages": messages}

    def add_security_headers(self, r):
        """
        Add security headers to a request
        """
        for header, value in self.security_headers:
            r.headers.set(header, value)
        return r

    def start(self, host: str, port: int, stay_open: bool = False):
        """
        Start the web server
        """
        uvicorn.run(app, host=host, port=port)
        self.running = True

    def stop(self, port):
        """
        Stop the flask web server by loading /shutdown.
        """
        self.__log.info("stopping server")

        if not self.running:
            return

        exit(4)
