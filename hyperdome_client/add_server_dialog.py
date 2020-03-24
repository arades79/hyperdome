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
from PyQt5 import QtWidgets, QtGui, QtCore
from . import threads
from .server import Server


class AddServerDialog(QtWidgets.QDialog):
    """
    Dialog for entering server connection details and or credentials.
    """

    server_added = QtCore.pyqtSignal(Server)
    is_counselor = False

    def __init__(self, common, session, parent):
        super(AddServerDialog, self).__init__(parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.session = session

        self.setWindowTitle("Add Hyperdome Server")
        self.setWindowIcon(QtGui.QIcon(common.get_resource_path("images/logo.png")))

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
        counselor_radio.toggled.connect(
            lambda: self.radio_switch(counselor_radio)
        )

        guest_radio = QtWidgets.QRadioButton()
        guest_radio.setText("Guest")
        guest_radio.setChecked(True)
        guest_radio.toggled.connect(lambda: self.radio_switch(guest_radio))

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

    def add_server(self):
        """
        Reciever for the add server dialog to handle the new server details.
        """
        server = Server(
            url=self.server_add_text.text(),
            nick=self.server_nick_text.text(),
            uname=self.counselor_username_input.text(),
            passwd=self.counselor_password_input.text(),
            is_counselor=self.is_counselor,
        )

        @QtCore.pyqtSlot(str)
        def set_server(_: str):
            self.add_server_button.setEnabled(True)
            self.server_added.emit(server)
            self.close()

        @QtCore.pyqtSlot(str)
        def bad_server(err: str):
            self.add_server_button.setEnabled(True)
            QtWidgets.QMessageBox(str=err).exec_()

        self.add_server_button.setEnabled(False)
        probe = threads.ProbeServerTask(self.session, server)
        probe.signals.success.connect(set_server)
        probe.signals.error.connect(bad_server)
        pool = QtCore.QThreadPool()
        pool.start(probe)
        pool.waitForDone(10000)
