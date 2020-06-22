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

import functools
import json
import typing

import autologging
import requests

from ..common.server import Server


def handle_requests_errors(fn: typing.Callable):
    """
    wraps a requests call to provide exception handling boilerplate
    for errors which are generic to any requests call
    """

    @functools.wraps(fn)
    @autologging.logged
    def wrapper(*args, **kwargs):
        try:
            response = fn(*args, **kwargs)
        except requests.ConnectionError:
            wrapper._log.warning("couldn't connect to server")
            raise
        except requests.Timeout:
            wrapper._log.warning("server timed out during request")
            raise
        except requests.HTTPError as e:
            wrapper._log.warning(f"{e.args[0]}")
            raise
        except:
            wrapper._log.exception("unexpected exception during request handling")
            raise
        else:
            return response

    return wrapper


@autologging.traced
@autologging.logged
class HyperdomeClientApi:
    """
    container class for hyperdome server API calls
    uses a requests session and server variable
    """

    COMPATIBLE_SERVERS = ["0.2", "0.2.0", "0.2.1", "0.3.0"]

    __log: autologging.logging.Logger  # makes linter happy about autologging

    def __init__(self, server: Server, session: requests.Session) -> None:
        self.server = server
        self.session = session

    @handle_requests_errors
    def signout_counselor(self, user_id: str):
        self.session.post(
            f"{self.server.url}/counselor_signout", data={"user_id": user_id}
        )

    @handle_requests_errors
    def counseling_complete(self, user_id: str):
        self.session.post(
            f"{self.server.url}/counseling_complete", data={"user_id": user_id}
        ).raise_for_status

    @handle_requests_errors
    def send_message(self, uid: str, message: str):
        """
        Send message to server provided using session for given user
        """
        return self.session.post(
            f"{self.server.url}/send_message", data={"message": message, "user_id": uid}
        )

    @handle_requests_errors
    def get_uid(self):
        """
        Ask server for a new UID for a new user session
        """
        response = self.session.get(f"{self.server.url}/generate_guest_id")
        response.raise_for_status()
        return response.text

    @handle_requests_errors
    def get_messages(self, uid: str):
        """
        collect new messages waiting on server for active session
        """
        response = self.session.get(
            f"{self.server.url}/collect_messages", data={"user_id": uid}
        )
        response_json = response.json()
        if response_json["chat_status"] == "CHAT_ACTIVE":
            return response_json["messages"]
        elif response["chat_status"] == "CHAT_OVER":
            raise requests.HTTPError(f"chat over", response)

    @handle_requests_errors
    def start_chat(
        self, uid: str, pub_key: str, signature: str = "",
    ):
        if self.server.is_counselor:
            return self.session.post(
                f"{self.server.url}/counselor_signin",
                data={
                    "pub_key": pub_key,
                    "signature": signature,
                    "username": self.server.username,
                },
            ).text

        else:
            return self.session.post(
                f"{self.server.url}/request_counselor",
                data={"guest_id": uid, "pub_key": pub_key},
            ).text

    @handle_requests_errors
    def probe_server(self):
        info = json.loads(self.session.get(f"{self.server.url}/probe").text)
        if info["name"] != "hyperdome":
            return "not hyperdome"
        if info["version"] not in self.COMPATIBLE_SERVERS:
            return "bad version"
        return ""

    @handle_requests_errors
    def get_guest_pub_key(self, uid: str):
        return self.session.get(
            f"{self.server.url}/poll_connected_guest", data={"counselor_id": uid}
        ).text

    @handle_requests_errors
    def signup_counselor(
        self, passcode: str, pub_key: str, signature: str,
    ):
        return self.session.post(
            f"{self.server.url}/counselor_signup",
            data={
                "username": self.server.username,
                "pub_key": pub_key,
                "signup_code": passcode,
                "signature": signature,
            },
        ).text
