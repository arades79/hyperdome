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
import typing
import functools
from PyQt5 import QtCore

from .add_server_dialog import Server
from hyperdome_server.onion import (BundledTorTimeout, TorErrorProtocolError,
                                    TorErrorAuthError,
                                    TorErrorUnreadableCookieFile,
                                    TorErrorMissingPassword,
                                    TorErrorSocketFile, TorErrorSocketPort,
                                    TorErrorAutomatic, TorErrorInvalidSetting,
                                    TorTooOld)


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
    Signin therapist, or request therapist session if user
    """
    signals = TaskSignals()

    def __init__(self,
                 server: Server,
                 session: requests.Session,
                 uid: str):
        super(StartChatTask, self).__init__()
        self.server = server
        self.session = session
        self.uid = uid

    def run(self):
        try:
            self.signals.success.emit(start_chat(
                self.server, self.session, self.uid))
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


def send_message(server: Server,
                 session: requests.Session,
                 uid: str,
                 message: str):
    """
    Send message to server provided using session for given user
    """
    if server.is_therapist:  # needs auth
        session.post(
            f"{server.url}/message_from_therapist",
            data={
                "username": server.username,
                "password": server.password,
                "message": message})
    else:  # normal user
        session.post(
            f'{server.url}/message_from_user',
            data={
                'message': message,
                'guest_id': uid})


def get_uid(server: Server,
            session: requests.Session):
    """
    Ask server for a new UID for a new user session
    """
    return session.get(
        f'{server.url}/generate_guest_id').text


def get_messages(server: Server,
                 session: requests.Session,
                 uid: str = ''):
    """
    collect new messages waiting on server for active session
    """
    # TODO: unify counselor and guest versions w/UID
    if server.is_therapist:
        messages_response = session.get(
            f"{server.url}/collect_therapist_messages",
            headers={"username": server.username,
                     "password": server.password})
        status = messages_response.status_code
        if status == 404:
            raise requests.HTTPError
        elif status == 200:
            return messages_response.text
        else:
            raise requests.RequestException

    elif uid:
        new_messages = session.get(
            f"{server.url}/collect_guest_messages",
            data={"guest_id": uid}).text
    else:
        new_messages = ''
    return new_messages


def start_chat(server: Server,
               session: requests.Session,
               uid: str):
    if server.is_therapist:
        session.post(f"{server.url}/therapist_signin",
                     data={"username": server.username,
                           "password": server.password})
        return ''
    else:
        return session.post(
            f"{server.url}/request_therapist",
            data={"guest_id": uid}).text


class GenericRequestTask(QtCore.QRunnable):
    """
    Generic Runnable for injecting function behavior
    """
    signals = TaskSignals()

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        try:
            success = self._func(*self._args, **self._kwargs)
            self.signals.success.emit(success)
        except ArgumentError as e:
            self.signals.error.emit(e)
        except HTTPException as e:
            self.signals.error.emit(e)

    def __del__(self):
        self.wait()

def create_task(success, error):
    """
    Decorator to transform function def into runnable task
    """
    def outer(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            task = GenericRequestTask(func, *args, **kwargs)
            task.signals.success.connect(success)
            task.signals.error.connect(error)
        return inner
    return outer





