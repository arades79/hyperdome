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
from queue import Queue
import secrets
from threading import Lock

from fastapi import HTTPException, FastAPI, Form

import logging

from . import models
from ..common.common import version

logger = logging.getLogger(__name__)

app = FastAPI()

# hyperdome server user tracking variables
counselors_available: set[str] = set()
active_chats: dict[str, Queue[str]] = dict()
guest_keys = dict()
counselor_keys = dict()
active_codes = set()

lock = Lock()


@app.get("/probe")
def probe():
    return {
        "name": "hyperdome",
        "version": version,
        "online": len(counselors_available),
    }


@app.post("/request_counselor")
def request_counselor(guest_id: str = Form(), guest_key: str = Form()):
    if not counselors_available:
        return ""
    with lock:
        chosen_counselor = secrets.choice(tuple(counselors_available))
        counselors_available.remove(chosen_counselor)
    active_chats[guest_key] = Queue()
    guest_keys[chosen_counselor] = guest_key
    counselor_key = counselor_keys.pop(chosen_counselor)
    active_chats[counselor_key] = Queue()
    return counselor_key


@app.get("/poll_connected_guest")
def poll_connected_guest(counselor_id: str = Form()):
    guest_key = guest_keys.pop(counselor_id, "")
    return guest_key


@app.post("/counseling_complete")
def counseling_complete(user_id: str = Form()):
    if user_id not in active_chats.keys():
        raise HTTPException(404, "no active chat")
    with lock:
        active_chats.pop(user_id)
    return "Chat Ended"


@app.post("/counselor_signout")
def counselor_signout(user_id: str = Form()):
    with lock:
        counselors_available.remove(user_id)
        counselor_keys.pop(user_id, "")
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
        logger.info(f"attempted counselor login failed verification {username=}")
        raise HTTPException(401, "Bad signature")
    sid = secrets.token_urlsafe(16)
    # will use capacity variable for this later
    counselors_available.add(sid)
    counselor_keys[sid] = pub_key
    logger.info(f"successful counselor login {username=}")
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
    if counselor.verify(signature, signup_code.encode()):
        models.db.session.add(counselor)
        models.db.session.commit()
        logger.info(f"new counselor {username=} added")

        return "Good"  # TODO: add better responses
    else:
        models.db.session.commit()
        logger.warning(
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
        active_chats[user_id].put_nowait(message)
    except KeyError:
        raise HTTPException(404, "no chat")
    return "Success"


@app.get("/collect_messages")
def collect_messages(user_id: str = Form()):
    messages: str = ""
    try:
        message_queue = active_chats[user_id]
        while not message_queue.empty():
            messages += f"{message_queue.get_nowait()}\n"
        chat_status = "CHAT_ACTIVE"
    except KeyError:
        chat_status = "NO_CHAT"
    return {"chat_status": chat_status, "messages": messages}
