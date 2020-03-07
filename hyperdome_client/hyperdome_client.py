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
from PyQt5 import QtCore, QtWidgets, QtGui

from hyperdome_server import strings

from .tor_connection_dialog import TorConnectionDialog
from .settings_dialog import SettingsDialog
from .widgets import Alert
from .add_server_dialog import AddServerDialog, Server
from . import threads
from . import encryption

import requests
import traceback


class HyperdomeClient(QtWidgets.QMainWindow):
    """
    OnionShareGui is the main window for the GUI that contains all of the
    GUI elements.
    """

    def __init__(self,
                 common,
                 onion,
                 qtapp: QtWidgets.QApplication,
                 app,
                 filenames,
                 config: bool = False,
                 local_only: bool = False):
        super(HyperdomeClient, self).__init__()

        # set application variables
        self.common = common
        self.onion = onion
        self.qtapp: QtWidgets.QApplication = qtapp
        self.app = app
        self.local_only: bool = local_only
        self.common.log('OnionShareGui', '__init__')

        # setup threadpool and tasks for async
        self.worker = QtCore.QThreadPool()
        self.get_messages_task: threads.GetMessagesTask = None
        self.send_message_task: threads.SendMessageTask = None
        self.get_uid_task: threads.GetUidTask = None
        self.probe_server_task: threads.ProbeServerTask = None

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._timer_callback)
        self.timer.setInterval(3500)

        # set window constants
        self.setMinimumWidth(500)
        self.setMinimumHeight(660)
        self.setWindowTitle('hyperdome')
        self.setWindowIcon(QtGui.QIcon(self.common.get_resource_path(
            'images/logo.png')))

        # make dialog for error messages
        self.error_window = Alert(self.common, '', autostart=False)

        # initialize session variables
        self.uid: str = ''
        self.chat_history: list = []
        self.servers: dict = dict()
        self.server: Server = Server()
        self.is_connected: bool = False
        self._session: requests.Session = None
        self.crypt = encryption.LockBox()

        # Load settings, if a custom config was passed in
        self.config = config
        if self.config:
            self.common.load_settings(self.config)

        # System tray
        menu = QtWidgets.QMenu()
        self.settings_action = menu.addAction(
            strings._('gui_settings_window_title'))
        self.settings_action.triggered.connect(self.open_settings)
        help_action = menu.addAction(strings._('gui_settings_button_help'))
        help_action.triggered.connect(SettingsDialog.help_clicked)
        exit_action = menu.addAction(strings._('systray_menu_exit'))
        exit_action.triggered.connect(self.close)

        self.system_tray = QtWidgets.QSystemTrayIcon(self)
        # The convention is Mac systray icons are always grayscale
        if self.common.platform == 'Darwin':
            self.system_tray.setIcon(QtGui.QIcon(self.common.get_resource_path(
                'images/logo_grayscale.png')))
        else:
            self.system_tray.setIcon(
                QtGui.QIcon(
                    self.common.get_resource_path('images/logo.png')))
        self.system_tray.setContextMenu(menu)
        self.system_tray.show()

        self.server_add_dialog = AddServerDialog(
            common=self.common, add_server_action=self.add_server)

        # chat pane
        self.settings_button = QtWidgets.QPushButton()
        self.settings_button.setDefault(False)
        self.settings_button.setFixedWidth(40)
        self.settings_button.setFixedHeight(50)
        self.settings_button.setIcon(QtGui.QIcon(
            self.common.get_resource_path('images/settings.png')))
        self.settings_button.clicked.connect(self.open_settings)
        self.settings_button.setStyleSheet(self.common.css['settings_button'])

        self.message_text_field = QtWidgets.QPlainTextEdit()
        self.message_text_field.setFixedHeight(50)
        self.message_text_field.setPlaceholderText('Enter message:')

        self.enter_button = QtWidgets.QPushButton("Send")
        self.enter_button.clicked.connect(self.send_message)
        self.enter_button.setFixedHeight(50)

        self.enter_text = QtWidgets.QHBoxLayout()
        self.enter_text.addWidget(self.message_text_field)
        self.enter_text.addWidget(self.enter_button)
        self.enter_text.addWidget(self.settings_button)

        self.chat_window = QtWidgets.QListWidget()
        self.chat_window.setWordWrap(True)
        self.chat_window.setWrapping(True)
        self.chat_window.addItems(self.chat_history)

        self.chat_pane = QtWidgets.QVBoxLayout()
        self.chat_pane.addWidget(self.chat_window, stretch=1)
        self.chat_pane.addLayout(self.enter_text)

        # server list view
        self.start_chat_button = QtWidgets.QPushButton()
        self.start_chat_button.setText('Start Chat')
        self.start_chat_button.setFixedWidth(100)
        self.start_chat_button_connection = self.start_chat_button.clicked.connect(
            self.start_chat)
        self.start_chat_button.setEnabled(False)

        self.server_dropdown = QtWidgets.QComboBox(self)
        self.server_dropdown.addItem("Select a Server")
        self.server_dropdown.addItem("Add New Server")
        self.server_dropdown.currentIndexChanged.connect(self.server_switcher)

        self.server_pane = QtWidgets.QHBoxLayout()
        self.server_pane.addWidget(self.server_dropdown)
        self.server_pane.addWidget(self.start_chat_button)

        # full view
        self.full_layout = QtWidgets.QVBoxLayout()
        self.full_layout.addLayout(self.server_pane)
        self.full_layout.addLayout(self.chat_pane)

        self.main_widget = QtWidgets.QWidget()
        self.main_widget.setLayout(self.full_layout)

        self.setCentralWidget(self.main_widget)
        self.show()

        # Start the "Connecting to Tor" dialog, which calls onion.connect()
        tor_con = TorConnectionDialog(self.common, self.qtapp, self.onion)
        tor_con.canceled.connect(self._tor_connection_canceled)
        tor_con.open_settings.connect(self._tor_connection_open_settings)
        if not self.local_only:
            tor_con.start()

    def send_message(self):
        """
        Send the contents of the message box to the server to be forwarded to
        either counsel or guest.
        """

        message = self.message_text_field.toPlainText()
        self.message_text_field.clear()

        if not self.is_connected and not self.uid:
            return self.handle_error("not in an active chat")

        enc_message = self.crypt.encrypt_outgoing_message(message)

        send_message = threads.SendMessageTask(
            self.server, self.session, self.uid, enc_message)
        send_message.signals.error.connect(self.handle_error)

        self.worker.start(send_message)
        self.chat_window.addItem(f"You: {message}")

    @QtCore.pyqtSlot(str)
    def on_history_added(self, messages: str):
        """
        Update UI with messages retrieved from server.
        """
        sender_name = "counselor" if self.server.is_counselor else "user"
        message_list = [f'{sender_name}: {self.crypt.decrypt_incoming_message(message)}'
                        for message in messages.split('\n') if message]
        self.chat_window.addItems(message_list)

    def get_uid(self):
        """
        Ask server for a new UID for a new user session
        """
        @QtCore.pyqtSlot(str)
        def after_id(uid: str):
            self.uid = uid
            self.start_chat_button.setEnabled(True)

        if self.timer.isActive():
            self.timer.stop()
        if not self.server.is_counselor:
            get_uid_task = threads.GetUidTask(self.server, self.session)
            get_uid_task.signals.success.connect(after_id)
            get_uid_task.signals.error.connect(self.handle_error)
            self.worker.start(get_uid_task)
        else:  # user is a counselor which will get uid later
            after_id('')  # use same callback without uid

    @QtCore.pyqtSlot(str)
    def handle_error(self, error: str):
        """
        take error string and assign it to the created alert window
        changes active window with new text
        and brings to focus if currently in the background.
        """
        self.error_window.setText(error)
        if self.error_window.isActiveWindow():
            self.error_window.setFocus()
        else:
            self.error_window.exec_()

    @property
    def session(self):
        """
        Lazy getter for tor proxy session.
        Ensures proxy isn't attempted until tor circuit established.
        """
        if self._session is None:
            self._session = requests.Session()
            if self.onion.is_authenticated():
                socks_address, socks_port = self.onion.get_tor_socks_port()
                self._session.proxies = {
                    'http': f'socks5h://{socks_address}:{socks_port}',
                    'https': f'socks5h://{socks_address}:{socks_port}'}
        return self._session

    def server_switcher(self):
        """
        Handle a switch to a different saved server by establishing a new
        connection and retrieving new UID.
        """
        self.chat_window.clear()
        self.message_text_field.clear()
        self.crypt.rotate()
        if self.is_connected:
            self.disconnect_chat()
        if (self.server_dropdown.currentIndex() ==
                self.server_dropdown.count() - 1):
            self.server_dropdown.setCurrentIndex(0)
            self.start_chat_button.setEnabled(False)
            self.server_add_dialog.exec_()
        elif self.server_dropdown.currentIndex():
            self.server = self.servers[self.server_dropdown.currentText()]
            self.get_uid()

    def start_chat(self):
        @QtCore.pyqtSlot(str)
        def after_start(counselor: str):
            if not self.server.is_counselor and not counselor:
                self.handle_error("No counselors available.")
                self.start_chat_button.setEnabled(True)
                return
            if self.server.is_counselor:
                self.uid = counselor
            self.is_connected = True
            self.get_messages_task = threads.GetMessagesTask(self.session,
                                                             self.server,
                                                             self.uid)
            self.get_messages_task.setAutoDelete(False)
            self.get_messages_task.signals.success.connect(
                self.on_history_added)
            self.timer.start()
            self.start_chat_button.setText("Disconnect")
            self.start_chat_button.clicked.disconnect(
                self.start_chat_button_connection)
            self.start_chat_button_connection = self.start_chat_button.clicked.connect(
                self.disconnect_chat)
            self.start_chat_button.setEnabled(True)

        self.start_chat_button.setEnabled(False)
        start_chat_task = threads.StartChatTask(
            self.server, self.session, self.uid, self.crypt.public_key)
        start_chat_task.signals.success.connect(after_start)
        start_chat_task.signals.error.connect(self.handle_error)
        self.worker.start(start_chat_task)

    def add_server(self, server):
        """
        Reciever for the add server dialog to handle the new server details.
        """
        @QtCore.pyqtSlot(str)
        def set_server(_: str):
            self.server_add_dialog.close()
            self.server_add_dialog.add_server_button.setEnabled(True)
            self.server = server
            self.servers[server.nick] = self.server
            self.server_dropdown.insertItem(1, server.nick)

        @QtCore.pyqtSlot(str)
        def bad_server(err: str):
            self.server_add_dialog.add_server_button.setEnabled(True)
            self.handle_error(err)

        self.server_add_dialog.add_server_button.setEnabled(False)
        probe = threads.ProbeServerTask(self.session, server)
        probe.signals.success.connect(set_server)
        probe.signals.error.connect(bad_server)
        self.worker.start(probe)

    def _tor_connection_canceled(self):
        """
        If the user cancels before Tor finishes connecting, ask if they want to
        quit, or open settings.
        """
        self.common.log('OnionShareGui', '_tor_connection_canceled')

        def ask():
            a = Alert(
                self.common,
                strings._('gui_tor_connection_ask'),
                QtWidgets.QMessageBox.Question,
                buttons=QtWidgets.QMessageBox.NoButton,
                autostart=False)
            settings_button = QtWidgets.QPushButton(
                strings._('gui_tor_connection_ask_open_settings'))
            quit_button = QtWidgets.QPushButton(
                strings._('gui_tor_connection_ask_quit'))
            a.addButton(settings_button, QtWidgets.QMessageBox.AcceptRole)
            a.addButton(quit_button, QtWidgets.QMessageBox.RejectRole)
            a.setDefaultButton(settings_button)
            a.exec_()

            if a.clickedButton() == settings_button:
                # Open settings
                self.common.log(
                    'OnionShareGui',
                    '_tor_connection_canceled',
                    'Settings button clicked')
                self.open_settings()

            if a.clickedButton() == quit_button:
                # Quit
                self.common.log(
                    'OnionShareGui',
                    '_tor_connection_canceled',
                    'Quit button clicked')

                # Wait 1ms for the event loop to finish, then quit
                QtCore.QTimer.singleShot(1, self.qtapp.quit)

        # Wait 100ms before asking
        QtCore.QTimer.singleShot(100, ask)

    def _tor_connection_open_settings(self):
        """
        The TorConnectionDialog wants to open the Settings dialog
        """
        self.common.log('OnionShareGui', '_tor_connection_open_settings')

        # Wait 1ms for the event loop to finish closing the TorConnectionDialog
        QtCore.QTimer.singleShot(1, self.open_settings)

    def open_settings(self):
        """
        Open the SettingsDialog.
        """
        self.common.log('OnionShareGui', 'open_settings')

        def reload_settings():
            self.common.log(
                'OnionShareGui',
                'open_settings',
                'settings have changed, reloading')
            self.common.settings.load()

            # We might've stopped the main requests timer if
            # a Tor connection failed.
            # If we've reloaded settings, we probably succeeded in obtaining
            # a new connection. If so, restart the timer.

        d = SettingsDialog(self.common, self.onion, self.qtapp, self.config,
                           self.local_only)
        d.settings_saved.connect(reload_settings)
        d.exec_()

    @QtCore.pyqtSlot()
    def _timer_callback(self):
        """
        Passed to timer to continually check for new messages on the server
        """
        if self.get_messages_task is not None:
            self.worker.tryStart(self.get_messages_task)

    def copy_url(self):
        """
        When the URL gets copied to the clipboard, display this \
        in the status bar.
        """
        self.common.log('OnionShareGui', 'copy_url')
        self.system_tray.showMessage(strings._('gui_copied_url_title'),
                                     strings._('gui_copied_url'))

    def copy_hidservauth(self):
        """
        When the stealth onion service HidServAuth gets copied to \
        the clipboard, display this in the status bar.
        """
        self.common.log('OnionShareGui', 'copy_hidservauth')
        self.system_tray.showMessage(strings._('gui_copied_hidservauth_title'),
                                     strings._('gui_copied_hidservauth'))

    def disconnect_chat(self):
        self.start_chat_button.setEnabled(False)
        self.timer.stop()
        self.worker.clear()
        if self.get_messages_task is not None:
            del self.get_messages_task
            self.get_messages_task = None
        if self.is_connected:
            self.worker.start(threads.EndChatTask(
                self.session, self.server, self.uid))
        if self.server.is_counselor:
            self.worker.start(threads.CounselorSignoutTask(
                self.session, self.server, self.uid))
        self.start_chat_button.setText('Start Chat')
        self.start_chat_button.clicked.disconnect(
            self.start_chat_button_connection)
        self.start_chat_button_connection = self.start_chat_button.clicked.connect(
            self.start_chat)
        self.start_chat_button.setEnabled(True)
        self.is_connected = False

    def closeEvent(self, event):
        """
        When the main window is closed, do some cleanup
        """
        self.common.log('OnionShareGui', 'closeEvent')
        self.disconnect_chat()

        self.hide()

        self.worker.waitForDone()
        self.worker.event(event)

        self.system_tray.hide()  # seemingly necessary

        if self.onion:
            self.onion.cleanup()
        if self.app:
            self.app.cleanup()
