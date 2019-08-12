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

        # start onionshare http service in new thread
        self.mode.web_thread = WebThread(self.mode)
        self.mode.web_thread.start()

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


class WebThread(QtCore.QThread):
    """
    Starts the web service
    """
    success = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)

    def __init__(self, mode):
        super(WebThread, self).__init__()
        self.mode = mode
        self.mode.common.log('WebThread', '__init__')

    def run(self):
        self.mode.common.log('WebThread', 'run')
        self.mode.app.choose_port()
        self.mode.web.start(self.mode.app.port,
                            self.mode.app.stay_open,
                            self.mode.common.settings.get('public_mode'),
                            self.mode.common.settings.get('slug'))


class PostRequestThread(QtCore.QThread):
    """
    Send message to server on another thread
    """
    success = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)

    def __init__(self,
                 session: requests.Session,
                 url: str = '',
                 data: dict = {}):
        super(PostRequestThread, self).__init__()
        self.session = session
        self.url = url
        self.data = data

    def __del__(self):
        self.wait()

    def run(self):
        try:
            response = self.session.post(self.url, self.data).text
            self.success.emit(response)
        except (requests.ConnectionError, requests.RequestException) as e:
            self.error.emit(str(e))


class GetMessagesThread(QtCore.QThread):
    """
    retrieve new messages on a fixed interval
    """
    success = QtCore.pyqtSignal(list)
    error = QtCore.pyqtSignal(str)

    def __init__(self, session: requests.Session, server: Server):
        super(GetMessagesThread, self).__init__()
        self.session = session
        self.server = server

    def __del__(self):
        self.wait()

    def run(self):
        while True:
            if self.server.is_therapist:
                new_messages = self.session.get(
                    f"{self.server.url}/collect_therapist_messages",
                    headers={"username": self.server.username,
                             "password": self.server.password}).text
                if new_messages:
                    new_messages = [f'Guest: {message}' for message
                                    in new_messages.split('\n')]
                    self.chat_window.addItems(new_messages)
            elif self.uid:
                new_messages = self.session.get(
                    f"{self.server.url}/collect_guest_messages",
                    data={"guest_id": self.uid}).text
                if new_messages:
                    new_messages = [f'{self.therapist}: {message}' for message
                                    in new_messages.split('\n')]
                    self.success.emit(new_messages)
            self.sleep(2)
