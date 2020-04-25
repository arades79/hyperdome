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
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            getattr(fn, "_log")
        except AttributeError:
            return fn(*args, **kwargs)
        try:
            response = fn(*args, **kwargs)
        except requests.ConnectionError:
            handle_requests_errors._log.warning("couldn't connect to server")
            raise
        except requests.Timeout:
            handle_requests_errors._log.warning("server timed out during request")
            raise
        except requests.HTTPError:
            raise
        else:
            return response

    return wrapper


@autologging.traced
@autologging.logged
@handle_requests_errors
def send_message(server: Server, session: requests.Session, uid: str, message: str):
    """
    Send message to server provided using session for given user
    """
    session.post(
        f"{server.url}/send_message", data={"message": message, "user_id": uid}
    )


@autologging.traced
@autologging.logged
@handle_requests_errors
def get_uid(server: Server, session: requests.Session):
    """
    Ask server for a new UID for a new user session
    """
    response = session.get(f"{server.url}/generate_guest_id")
    try:
        response.raise_for_status()
    except requests.HTTPError:
        get_uid._log.exception(response.text)
        raise
    else:
        return response.text


@autologging.traced
@autologging.logged
@handle_requests_errors
def get_messages(server: Server, session: requests.Session, uid: str):
    """
    collect new messages waiting on server for active session
    """
    response = session.get(
        f"{server.url}/collect_messages", data={"user_id": uid}
    ).json()
    try:
        response.raise_for_status()
    except requests.HTTPError:
        pass


@autologging.traced
@autologging.logged
@handle_requests_errors
def start_chat(
    server: Server,
    session: requests.Session,
    uid: str,
    pub_key: str,
    signature: str = "",
):
    if server.is_counselor:
        return session.post(
            f"{server.url}/counselor_signin",
            data={
                "pub_key": pub_key,
                "signature": signature,
                "username": server.username,
            },
        ).text

    else:
        return session.post(
            f"{server.url}/request_counselor",
            data={"guest_id": uid, "pub_key": pub_key},
        ).text


COMPATIBLE_SERVERS = ["0.2", "0.2.0", "0.2.1"]


@autologging.traced
@autologging.logged
@handle_requests_errors
def probe_server(server: Server, session: requests.Session):
    info = json.loads(session.get(f"{server.url}/probe").text)
    if info["name"] != "hyperdome":
        return "not hyperdome"
    if info["version"] not in COMPATIBLE_SERVERS:
        return "bad version"
    return ""


@autologging.traced
@autologging.logged
@handle_requests_errors
def get_guest_pub_key(server: Server, session: requests.Session, uid: str):
    return session.get(
        f"{server.url}/poll_connected_guest", data={"counselor_id": uid}
    ).text


@autologging.traced
@autologging.logged
@handle_requests_errors
def signup_counselor(
    server: Server,
    session: requests.Session,
    passcode: str,
    pub_key: str,
    signature: str,
):
    return session.post(
        f"{server.url}/counselor_signup",
        data={
            "username": server.username,
            "pub_key": pub_key,
            "signup_code": passcode,
            "signature": signature,
        },
    ).text
