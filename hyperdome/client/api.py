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


class ServerNotSupported(Exception):
    """
    client does not support the server's API version
    """


@autologging.traced
@autologging.logged
class HyperdomeClientApi:
    """
    container class for hyperdome server API calls
    uses a requests session and server variable
    """

    COMPATIBLE_SERVERS = ["0.2.1"]
    API_VERSION = "v1"

    __log: autologging.logging.Logger  # makes linter happy about autologging

    def __init__(self, server: Server, session: requests.Session) -> None:
        self.host = server.url
        self.user = "counselors" if server.is_counselor else "guests"
        self.is_counselor = server.is_counselor
        self.username = server.username
        self.pub_key = server.key
        self.session = session
        self.url = ""
        self.uid = ""

    @handle_requests_errors
    def end_session(self, user_id: str):
        self.session.delete(f"{self.url}/{self.user}/{self.uid}").raise_for_status()

    @handle_requests_errors
    def signout_guest(self, user_id: str):
        self.session.delete(f"{self.url}/guests/{self.uid}").raise_for_status()

    @handle_requests_errors
    def counseling_complete(self, user_id: str):
        self.session.post(
            f"{self.url}/counseling_complete", data={"user_id": user_id}
        ).raise_for_status()

    @handle_requests_errors
    def send_message(self, message: str):
        """
        Send message to server provided using session for given user
        """
        return self.session.post(
            f"{self.url}/{self.user}/{self.uid}/chat", json={"message": message}
        )

    @handle_requests_errors
    def get_uid(self, pub_key: str, signature: str):
        """
        Ask server for a new UID for a new user session
        """
        response = self.session.post(
            f"{self.url}/guests", json={"pub_key": pub_key, "signature": signature}
        )
        response.raise_for_status()
        return response.json()["guest"]

    @handle_requests_errors
    def get_messages(self):
        """
        collect new messages waiting on server for active session
        """
        response = self.session.get(
            f"{self.url}/{self.user}/{self.uid}/chat/{self.count}"
        )
        response.raise_for_status()
        return response.json()["messages"]

    @handle_requests_errors
    def sign_in(
        self, signature: str, pub_key = ""
    ):
        data = {
                    "pub_key": self.pub_key,
                    "signature": signature,
                    "username": self.username,
                } if self.is_counselor else {"pub_key": pub_key, "signature": signature}
        self.session.post(
            f"{self.url}/{self.user}/",
            json=data
        )

    @handle_requests_errors
    def probe_server(self):
        info = self.session.get(f"{self.host}/hyperdome/api/").json()
        api_versions: list = info.get("api", [])
        hyperdome_version = info.get("version", "")
        if (
            hyperdome_version in self.COMPATIBLE_SERVERS
            or self.API_VERSION in api_versions
        ):
            self.url = f"{self.host}/hyperdome/api/v1/"
            return self.url
        else:
            raise ServerNotSupported("this client only supports hyperdome api v1")

    @handle_requests_errors
    def get_guest_pub_key(self):
        return self.session.get(f"{self.url}/guests/{self.uid}/").json()["guest"]

    @handle_requests_errors
    def signup_counselor(
        self, passcode: str, pub_key: str, signature: str,
    ):
        return self.session.post(
            f"{self.url}/counselors",
            data={
                "username": self.server.username,
                "pub_key": pub_key,
                "signup_code": passcode,
                "signature": signature,
            },
        ).text
