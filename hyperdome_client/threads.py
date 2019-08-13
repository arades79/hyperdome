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


class GenricTask(QtCore.QRunnable):
    """
    take a zero parameter function and run it
    """
    success = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)

    @QtCore.pyqtSlot(typing.Callable[[],None])
    def __init__(self, f: typing.Callable[[],None]):
        self.f = f

    def run(self):
        self.f()


class GetMessagesTask(QtCore.QRunnable):
    """
    retrieve new messages on a fixed interval
    """
    success = QtCore.pyqtSignal(list)
    error = QtCore.pyqtSignal(str)

    def __init__(self, session: requests.Session, server: Server, uid: str):
        super(GetMessagesTask, self).__init__()
        self.session = session
        self.server = server
        self.uid = uid

    def __del__(self):
        self.wait()

    def run(self):
        while True:
            try:
                self.success.emit(
                    get_messages(self.server, self.session, self.uid))
            except:
                self.error.emit("Error in get messages request")
                break
            self.sleep(2)

def send_message(server: Server,
                 session: requests.Session,
                 uid: str,
                 message: str):
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
    # TODO: unify counselor and guest versions w/UID
    if server.is_therapist:
        new_messages = session.get(
            f"{server.url}/collect_therapist_messages",
            headers={"username": server.username,
                     "password": server.password}).text
    elif uid:
        new_messages = session.get(
            f"{server.url}/collect_guest_messages",
            data={"guest_id": uid}).text
    else:
        new_messages = ''
    return new_messages