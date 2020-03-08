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
import time
import requests
from PyQt5 import QtCore

from .add_server_dialog import Server
from hyperdome_server.onion import (BundledTorTimeout, TorErrorProtocolError,
                                    TorErrorAuthError,
                                    TorErrorUnreadableCookieFile,
                                    TorErrorMissingPassword,
                                    TorErrorSocketFile, TorErrorSocketPort,
                                    TorErrorAutomatic, TorErrorInvalidSetting,
                                    TorTooOld)
from werkzeug.exceptions import MethodNotAllowed
import json
import functools

class OnionThread(QtCore.QThread):
    """
    Starts the onion service, and waits for it to finish
    """
    success = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def __init__(self, mode):
        super(OnionThread, self).__init__()
        self.mode = mode
        self.mode.common.log('OnionThread', '__init__')

        # allow this thread to be terminated
        self.setTerminationEnabled()

    def run(self):
        self.mode.common.log('OnionThread', 'run')

        self.mode.app.stay_open = not self.mode.common.settings.get(
            'close_after_first_download')

        # wait for modules in thread to load, preventing a thread-related
        # cx_Freeze crash
        time.sleep(0.2)

        try:
            self.mode.app.start_onion_service()
            self.success.emit()

        except (TorTooOld, TorErrorInvalidSetting, TorErrorAutomatic,
                TorErrorSocketPort, TorErrorSocketFile,
                TorErrorMissingPassword, TorErrorUnreadableCookieFile,
                TorErrorAuthError, TorErrorProtocolError, BundledTorTimeout,
                OSError) as e:
            self.error.emit(e.args[0])
            return


class TaskSignals(QtCore.QObject):
    success = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)


class SendMessageTask(QtCore.QRunnable):
    """
    send client message to server
    """
    signals = TaskSignals()

    def __init__(self,
                 server: Server,
                 session: requests.Session,
                 uid: str,
                 message: str):
        super(SendMessageTask, self).__init__()
        self.server = server
        self.session = session
        self.uid = uid
        self.message = message

    def run(self):
        try:
            send_message(self.server, self.session, self.uid, self.message)
        except requests.RequestException:
            self.signals.error.emit("Couldn't send message")


class GetUidTask(QtCore.QRunnable):
    """
    Get a UID from the server
    """
    signals = TaskSignals()

    def __init__(self,
                 server: Server,
                 session: requests.Session):
        super(GetUidTask, self).__init__()
        self.server = server
        self.session = session

    def run(self):
        try:
            uid = get_uid(self.server, self.session)
            self.signals.success.emit(uid)
        except requests.RequestException:
            self.signals.error.emit("couldn't get UID")


class StartChatTask(QtCore.QRunnable):
    """
    Signin counselor, or request counselor session if user
    """
    signals = TaskSignals()

    def __init__(self,
                 server: Server,
                 session: requests.Session,
                 uid: str,
                 pub_key: bytes):
        super(StartChatTask, self).__init__()
        self.server = server
        self.session = session
        self.uid = uid
        self.pub_key = pub_key

    def run(self):
        try:
            self.signals.success.emit(start_chat(
                self.server, self.session, self.uid, self.pub_key))
        except requests.RequestException:
            self.signals.error.emit("Couldn't start a chat session")


class GetMessagesTask(QtCore.QRunnable):
    """
    retrieve new messages on a fixed interval
    """
    signals = TaskSignals()

    def __init__(self, session: requests.Session, server: Server, uid: str):
        super(GetMessagesTask, self).__init__()
        self.session = session
        self.server = server
        self.uid = uid

    def run(self):
        try:
            new_messages = get_messages(self.server, self.session, self.uid)
            self.signals.success.emit(new_messages)
        except requests.HTTPError:
            self.signals.error.emit("Counselor not in chat")
        except requests.RequestException:
            self.signals.error.emit("Error in get messages request")
        except MethodNotAllowed:
            self.signals.error.emit("not allowed")


class ProbeServerTask(QtCore.QRunnable):
    """
    probe server for confirmation of hyperdome api
    and api version compatibility
    """
    signals = TaskSignals()

    def __init__(self, session: requests.Session, server: Server):
        super(ProbeServerTask, self).__init__()
        self.session = session
        self.server = server

    def run(self):
        try:
            status = probe_server(self.server, self.session)
            if status:
                raise Exception()

            self.signals.success.emit('good')
        except:
            self.signals.error.emit('server incompatible')


class EndChatTask(QtCore.QRunnable):
    """
    inform the server that the current chat session is concluded,
    freeing up the counselor for a new guest, and disconnecting the guest
    """
    signals = TaskSignals()

    def __init__(self, session: requests.Session, server: Server, uid: str):
        super(EndChatTask, self).__init__()
        self.session = session
        self.server = server
        self.uid = uid

    def run(self):
        try:
            self.session.post(f"{self.server.url}/counseling_complete",
                              data={'user_id': self.uid})
            self.signals.success.emit('good')
        except:
            self.signals.error.emit("you're stuck here now")


class CounselorSignoutTask(QtCore.QRunnable):
    """
    deregister counselor identified from active list,
    stopping them from receiving additional guests
    """
    signals = TaskSignals()

    def __init__(self, session: requests.Session, server: Server, uid: str):
        super(CounselorSignoutTask, self).__init__()
        self.session = session
        self.server = server
        self.uid = uid

    def run(self):
        try:
            self.session.post(f"{self.server.url}/counselor_signout",
                              data={"user_id": self.uid})
            self.signals.success.emit('good')
        except:
            self.signals.error.emit("you're stuck here now")

class PollForConnectedGuestTask(QtCore.QRunnable):
    """
    ask server if a guest has requested to connect yet
    and return the public key when they have
    """
    signals = TaskSignals()

    def __init__(self, session: requests.Session, server: Server, uid: str):
        super(PollForConnectedGuestTask, self).__init__()
        self.task = functools.partial(get_guest_pub_key, server, session, uid)

    def run(self):
        try:
            self.signals.success.emit(self.task())
        except:
            self.signals.error.emit("problem getting guest pubkey")



def send_message(server: Server,
                 session: requests.Session,
                 uid: str,
                 message: str):
    """
    Send message to server provided using session for given user
    """
    session.post(
        f'{server.url}/send_message',
        data={
            'message': message,
            'user_id': uid})


def get_uid(server: Server,
            session: requests.Session):
    """
    Ask server for a new UID for a new user session
    """
    if server.is_counselor:
        uid = session.post(f"{server.url}/counselor_signin",
                           files={"username": server.username,
                                 "password": server.password}).text
    else:
        uid = session.get(
            f'{server.url}/generate_guest_id').text
    return uid


def get_messages(server: Server,
                 session: requests.Session,
                 uid: str):
    """
    collect new messages waiting on server for active session
    """
    return session.get(
        f"{server.url}/collect_messages",
        data={"user_id": uid}).text


def start_chat(server: Server,
               session: requests.Session,
               uid: str,
               pub_key: str):
    if server.is_counselor:
        return session.get(f"{server.url}/counselor_signin",
                           data={"pub_key": pub_key}).text

    else:
        return session.post(
            f"{server.url}/request_counselor",
            data={"guest_id": uid, "pub_key": pub_key}).text


COMPATIBLE_SERVERS = ['2.0']


def probe_server(server: Server,
                 session: requests.Session):
    info = json.loads(session.get(f"{server.url}/probe").text)
    if info['name'] != 'hyperdome':
        return 'not hyperdome'
    if info['version'] not in COMPATIBLE_SERVERS:
        return 'bad version'
    return ''

def get_guest_pub_key(server: Server,
               session: requests.Session,
               uid: str):
    return session.get(
        f"{server.url}/poll_connected_guest",
        data={"counselor_id": uid}).text
