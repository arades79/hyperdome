# -*- coding: utf-8 -*-
"""
Copyright (C) 2019 Skyelar Craver

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



from PyQt5 import QtCore, QtWidgets, QtGui
import sys, platform, datetime, re

from onionshare import strings, common
from onionshare.settings import Settings
from onionshare.onion import *

class ChatWidget(QtWidgets.QWidget):
    
    def __init__(self, qtapp, server_list, chat_history, message_sender, settings_button):
        super(ChatWidget, self).__init__()

        self.qtapp = qtapp
        self.message_sender = message_sender

        self.message_text_field = QtWidgets.QPlainTextEdit()
        self.message_text_field.setFixedHeight(50)

        self.enter_button = QtWidgets.QPushButton("Send")
        self.enter_button.clicked.connect(self.chat_submit)
        self.enter_button.setFixedHeight(50)

        self.enter_text = QtWidgets.QHBoxLayout()
        self.enter_text.addWidget(self.message_text_field)
        self.enter_text.addWidget(self.enter_button)

        self.chat_history = QtWidgets.QListWidget()
        self.chat_history.addItems(chat_history)

        self.chat_pane = QtWidgets.QVBoxLayout()
        self.chat_pane.addWidget(self.chat_history, stretch=1)
        self.chat_pane.addLayout(self.enter_text)

        self.server_list = QtWidgets.QListWidget()
        self.server_list.addItems(server_list)
        self.server_list.setFixedWidth(200)

        self.add_server_button = QtWidgets.QPushButton('Add Server')
        self.add_server_button.setFixedHeight(50)
        self.add_server_button.setFixedWidth(155)

        self.server_buttons = QtWidgets.QHBoxLayout()
        self.server_buttons.addWidget(settings_button)
        self.server_buttons.addWidget(self.add_server_button)

        self.server_pane = QtWidgets.QVBoxLayout()
        self.server_pane.addWidget(self.server_list)
        self.server_pane.addLayout(self.server_buttons)

        self.full_layout = QtWidgets.QHBoxLayout()
        self.full_layout.addLayout(self.server_pane)
        self.full_layout.addLayout(self.chat_pane)
        self.setLayout(self.full_layout)


    def chat_submit(self):
        message = self.message_text_field.toPlainText()
        self.chat_history.addItem('You: ' + message)
        self.message_text_field.clear()
        self.message_sender(message)
        
