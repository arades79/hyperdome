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
from PyQt5 import QtWidgets, QtGui
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import base64


class Server(object):
    """
    Holder class for server connection details
    """

    class InvalidOnionAddress(Exception):
        """
        The onion address provided does not contain a valid v3 public key
        """

        pass

    def __init__(self, url="", nick="", uname="", passwd="", is_counselor=False):
        self.url = url
        if url:
            self._check_url()
        self.nick = nick
        self.username = uname
        self.password = passwd
        self.is_counselor = is_counselor

    def _check_url(self):
        """
        Ensure URL is properly formatted
        """

        if not (self.url.startswith(("http://", "https://"))):
            self.url = f"http://{self.url}"
        if not self.url.endswith(".onion"):
            self.url = f"{self.url}.onion"

        onion_key = self.url[7:-6]
        key_len = len(onion_key)
        last_char = onion_key[-1]

        if key_len != 56 or last_char != "d":
            # TODO: add debugging logger
            # print(f"{key_len=}\t{last_char=}")
            raise self.InvalidOnionAddress()


class AddServerDialog(QtWidgets.QDialog):
    """
    Dialog for entering server connection details and or credentials.
    """

    def __init__(self, common, add_server_action):
        super(AddServerDialog, self).__init__()

        self.is_counselor = False

        self.setWindowTitle("Add Hyperdome Server")
        self.setWindowIcon(QtGui.QIcon(common.get_resource_path("images/logo.png")))

        def add_server():
            try:
                server = self._make_server_from_fields()
                add_server_action(server)
            except Server.InvalidOnionAddress:
                self.reject()


        self.add_server_button = QtWidgets.QPushButton("Add Server")
        self.add_server_button.clicked.connect(add_server)

        self.server_add_text = QtWidgets.QLineEdit()
        self.server_add_text.setFixedWidth(400)
        self.server_add_text.setPlaceholderText("Server URL:")

        self.server_nick_text = QtWidgets.QLineEdit()
        self.server_nick_text.setFixedWidth(400)
        self.server_nick_text.setPlaceholderText("Nickname:")

        self.counselor_radio = QtWidgets.QRadioButton()
        self.counselor_radio.setText("Counselor")
        self.counselor_radio.toggled.connect(
            lambda: self.radio_switch(self.counselor_radio)
        )

        self.guest_radio = QtWidgets.QRadioButton()
        self.guest_radio.setText("Guest")
        self.guest_radio.setChecked(True)
        self.guest_radio.toggled.connect(lambda: self.radio_switch(self.guest_radio))

        self.radio_buttons = QtWidgets.QHBoxLayout()
        self.radio_buttons.addWidget(self.counselor_radio)
        self.radio_buttons.addWidget(self.guest_radio)

        self.counselor_username_input = QtWidgets.QLineEdit()
        self.counselor_username_input.setPlaceholderText("Username:")
        self.counselor_username_input.setFixedWidth(200)
        self.counselor_username_input.hide()

        self.counselor_password_input = QtWidgets.QLineEdit()
        self.counselor_password_input.setPlaceholderText("Password:")
        self.counselor_password_input.setFixedWidth(200)
        self.counselor_password_input.hide()

        self.counselor_credentials = QtWidgets.QHBoxLayout()
        self.counselor_credentials.addWidget(self.counselor_username_input)
        self.counselor_credentials.addWidget(self.counselor_password_input)

        self.server_dialog_layout = QtWidgets.QVBoxLayout()
        self.server_dialog_layout.addWidget(self.server_add_text)
        self.server_dialog_layout.addWidget(self.server_nick_text)
        self.server_dialog_layout.addLayout(self.radio_buttons)
        self.server_dialog_layout.addLayout(self.counselor_credentials)
        self.server_dialog_layout.addWidget(self.add_server_button)

        self.setLayout(self.server_dialog_layout)

    def _make_server_from_fields(self):
        """
        Take text fields and package into server object to pass.
        """
        url = self.server_add_text.text()
        nick = self.server_nick_text.text()
        uname = self.counselor_username_input.text()
        passwd = self.counselor_password_input.text()
        is_counselor = self.is_counselor

        return Server(
            url=url, nick=nick, uname=uname, passwd=passwd, is_counselor=is_counselor
        )

    def radio_switch(self, radio_switch):
        """
        Show or hide crediential fields based on user type selected.
        """
        if radio_switch.text() == "Counselor":
            self.is_counselor = True
            self.counselor_username_input.show()
            self.counselor_password_input.show()
        else:
            self.is_counselor = False
            self.counselor_username_input.hide()
            self.counselor_password_input.hide()

    def closeEvent(self, event):
        """
        Cleanup for when window is closed.
        """
        self.counselor_username_input.clear()
        self.counselor_password_input.clear()
        self.server_add_text.clear()
        self.server_nick_text.clear()
        self.done(0)
