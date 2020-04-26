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

from hyperdome.client.api import HyperdomeClientApi
from PyQt5 import QtCore, QtGui, QtWidgets
import autologging

from . import tasks, api
from ..common.common import resource_path
from ..common.encryption import LockBox
from ..common.server import Server


@autologging.logged
class AddServerDialog(QtWidgets.QDialog):
    """
    Dialog for entering server connection details and or credentials.
    """

    def __init__(self, parent: QtCore.QObject):
        super(AddServerDialog, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.session = parent.session
        self.worker = parent.worker

        self.error_message = QtWidgets.QMessageBox(self)

        self.setWindowTitle("Add Hyperdome Server")
        self.setWindowIcon(
            QtGui.QIcon(str(resource_path / "images/hyperdome_logo_100.png"))
        )

        self.is_counselor = False

        self.add_server_button = QtWidgets.QPushButton("Add Server")
        self.add_server_button.clicked.connect(self.add_server)

        self.server_add_text = QtWidgets.QLineEdit()
        self.server_add_text.setFixedWidth(400)
        self.server_add_text.setPlaceholderText("Server URL:")

        self.server_nick_text = QtWidgets.QLineEdit()
        self.server_nick_text.setFixedWidth(400)
        self.server_nick_text.setPlaceholderText("Nickname:")

        counselor_radio = QtWidgets.QRadioButton()
        counselor_radio.setText("Counselor")
        counselor_radio.toggled.connect(self.radio_switch)

        guest_radio = QtWidgets.QRadioButton()
        guest_radio.setText("Guest")
        guest_radio.setChecked(True)

        radio_buttons = QtWidgets.QHBoxLayout()
        radio_buttons.addWidget(counselor_radio)
        radio_buttons.addWidget(guest_radio)

        self.counselor_username_input = QtWidgets.QLineEdit()
        self.counselor_username_input.setPlaceholderText("Username:")
        self.counselor_username_input.setFixedWidth(200)
        self.counselor_username_input.hide()

        self.counselor_password_input = QtWidgets.QLineEdit()
        self.counselor_password_input.setPlaceholderText("Password:")
        self.counselor_password_input.setFixedWidth(200)
        self.counselor_password_input.setEchoMode(
            QtWidgets.QLineEdit.PasswordEchoOnEdit
        )
        self.counselor_password_input.hide()

        self.counselor_credentials = QtWidgets.QHBoxLayout()
        self.counselor_credentials.addWidget(self.counselor_username_input)
        self.counselor_credentials.addWidget(self.counselor_password_input)

        self.server_dialog_layout = QtWidgets.QVBoxLayout()
        self.server_dialog_layout.addWidget(self.server_add_text)
        self.server_dialog_layout.addWidget(self.server_nick_text)
        self.server_dialog_layout.addLayout(radio_buttons)
        self.server_dialog_layout.addLayout(self.counselor_credentials)
        self.server_dialog_layout.addWidget(self.add_server_button)

        self.setLayout(self.server_dialog_layout)

    def radio_switch(self, is_toggled):
        """
        Show or hide crediential fields based on user type selected.
        """
        self.is_counselor = is_toggled
        self.counselor_credentials.setEnabled(is_toggled)
        self.counselor_username_input.setVisible(is_toggled)
        self.counselor_password_input.setVisible(is_toggled)

    def add_server(self):
        """
        Receiver for the add server dialog to handle the new server details.
        """
        try:
            self.server = Server(
                url=self.server_add_text.text(),
                nick=self.server_nick_text.text(),
                username=self.counselor_username_input.text(),
                is_counselor=self.is_counselor,
            )
        except Server.InvalidOnionAddress:
            self.__log.warning("invalid onion address")
            self.error_message.setText("Invalid onion address!")
            self.error_message.exec_()
            return

        self.add_server_button.setEnabled(False)
        self.add_server_button.setText("Checking...")

        self.client = api.HyperdomeClientApi(self.server, self.session)

        run_probe_then = tasks.run_after_task(
            tasks.QtTask(self.client.probe_server), self.bad_server
        )

        if self.server.is_counselor:
            run_probe_then(self.signup)
        else:
            run_probe_then(self.set_server)

    @QtCore.pyqtSlot(object)
    def set_server(self, _):
        self.done(0)

    @QtCore.pyqtSlot(object)
    def signup(self, _):
        signer = LockBox()
        signer.make_signing_key()
        self.server.key = signer.export_key("123")  # TODO: use user provided password
        passcode = self.counselor_password_input.text()
        signature = signer.sign_message(passcode)
        run_signup_then = tasks.run_after_task(
            tasks.QtTask(
                self.client.signup_counselor,
                passcode,
                signer.public_signing_key,
                signature,
            ),
            self.bad_server,
        )
        run_signup_then(self.set_server)

    @QtCore.pyqtSlot(Exception)
    def bad_server(self, err: Exception):
        try:
            raise err
        except Exception as err:
            self.__log.exception("exception from add server task")
        self.add_server_button.setEnabled(True)
        self.add_server_button.setText("Add Server")
        self.error_message.setText("bad server")
        self.error_message.exec_()

    def get_server(self):
        return self.server

    def closeEvent(self, event):
        self.done(1)
        return super().closeEvent(event)
