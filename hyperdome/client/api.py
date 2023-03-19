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

import json
from typing import ParamSpec, Callable, Concatenate
import autologging
from PyQt5.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)
from PyQt5.QtCore import QUrl, pyqtSlot

from ..common.server import Server


FnParams = ParamSpec("FnParams")
CallbackParams = ParamSpec("CallbackParams")


def attach_callback(
    fn: Callable[Concatenate[Callable[CallbackParams, None], FnParams], None],
    *args: FnParams.args,
    **kwargs: FnParams.kwargs,
) -> Callable[[Callable[CallbackParams, None]], None]:
    def decorate(callback: Callable[CallbackParams, None]) -> None:
        return fn(callback, *args, **kwargs)

    return decorate


def response_handler(reply: QNetworkReply):
    def decorator(fn: Callable[[str], None]):
        @pyqtSlot()
        def wrapper() -> None:
            response = str(reply.readAll())
            fn(response)

        reply.readyRead.connect(wrapper)

    return decorator


@autologging.traced
@autologging.logged
class HyperdomeClientApi:
    """
    container class for hyperdome server API calls
    uses a requests session and server variable
    """

    COMPATIBLE_SERVERS = ["0.2", "0.2.0", "0.2.1", "0.3.0"]

    __log: autologging.logging.Logger  # makes linter happy about autologging

    def __init__(self, server: Server, session: QNetworkAccessManager) -> None:
        self.session = session
        self.server = server

    def signout_counselor(self, callback: Callable[..., None], user_id: str):
        request = QNetworkRequest(QUrl(f"{self.server.url}/counselor_signout"))
        data = json.dumps({"user_id": user_id}).encode()

        @response_handler(self.session.post(request, data))
        def parse_response(body: str):
            callback(body)

    def counseling_complete(self, callback: Callable[[], None], user_id: str):
        request = QNetworkRequest(QUrl(f"{self.server.url}/counseling_complete"))
        data = json.dumps({"user_id": user_id}).encode()

        @response_handler(self.session.post(request, data))
        def handle_response(body: str):
            callback()

    def send_message(self, callback: Callable[[], None], uid: str, message: str):
        """
        Send message to server provided using session for given user
        """
        request = QNetworkRequest(QUrl(f"{self.server.url}/send_message"))
        data = json.dumps({"message": message, "user_id": uid}).encode()

        @response_handler(self.session.post(request, data))
        def handler(body: str):
            callback()

    def get_uid(self, callback: Callable[[str], None]):
        """
        Ask server for a new UID for a new user session
        """
        request = QNetworkRequest(QUrl(f"{self.server.url}/generate_guest_id"))

        @response_handler(self.session.get(request))
        def handler(body: str):
            callback(body)

    def get_messages(self, callback: Callable[[str], None], uid: str):
        """
        collect new messages waiting on server for active session
        """
        request = QNetworkRequest(QUrl(f"{self.server.url}/collect_messages/{uid}"))

        @response_handler(self.session.get(request))
        def handler(body: str):
            callback(body)

    def start_chat(
        self,
        callback: Callable[[str], None],
        uid: str,
        pub_key: str,
        signature: str = "",
    ):

        if self.server.is_counselor:
            request = QNetworkRequest(QUrl(f"{self.server.url}/counselor_signin"))
            data = json.dumps(
                {
                    "pub_key": pub_key,
                    "signature": signature,
                    "username": self.server.username,
                }
            ).encode()

            @response_handler(
                self.session.post(
                    request,
                    data,
                )
            )
            def handler(body: str):
                callback(body)

        else:
            request = QNetworkRequest(QUrl(f"{self.server.url}/request_counselor"))
            data = json.dumps({"guest_id": uid, "pub_key": pub_key}).encode()

            @response_handler(self.session.post(request, data))
            def handler(body: str):
                callback(body)

        callback("")

    def probe_server(self, callback: Callable[[], None]):
        request = QNetworkRequest(QUrl(f"{self.server.url}/probe"))

        @response_handler(self.session.get(request))
        def handler(body: str):
            callback()

    def get_guest_pub_key(self, callback: Callable[[str], None], uid: str):
        request = QNetworkRequest(QUrl(f"{self.server.url}/poll_connected_guest/{uid}"))

        @response_handler(self.session.get(request))
        def handler(body: str):
            callback(body)

    def signup_counselor(
        self, callback: Callable[[], None], passcode: str, pub_key: str, signature: str
    ):
        request = QNetworkRequest(QUrl(f"{self.server.url}/counselor_signup"))
        data = json.dumps(
            {
                "username": self.server.username,
                "pub_key": pub_key,
                "signup_code": passcode,
                "signature": signature,
            }
        ).encode()

        @response_handler(
            self.session.post(
                request,
                data,
            )
        )
        def handler(body: str):
            callback()
