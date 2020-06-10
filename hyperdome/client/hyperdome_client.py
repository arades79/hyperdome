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
import json

from PyQt5 import QtCore, QtGui, QtWidgets
import autologging
import requests

from hyperdome.common.common import Settings

from . import api, tasks
from ..common import strings
from ..common import encryption
from ..common.common import resource_path
from ..common.server import Server
from .add_server_dialog import AddServerDialog
from .settings_dialog import SettingsDialog
from .tor_connection_dialog import TorConnectionDialog
from .widgets import Alert


@autologging.logged
class HyperdomeClient(QtWidgets.QMainWindow):
    """
    hyperdome is the main window for the GUI that contains all of the
    GUI elements.
    """

    def __init__(
        self,
        settings,
        onion,
        qtapp: QtWidgets.QApplication,
        app,
        filenames,
        config: str = "",
        local_only: bool = False,
    ):
        super(HyperdomeClient, self).__init__()

        # set application variables
        self.settings = settings
        self.onion = onion
        self.qtapp: QtWidgets.QApplication = qtapp
        self.app = app
        self.local_only: bool = local_only

        # setup interval task attributes
        self.poll_guest_key_task: tasks.QtIntervalTask = None
        self.get_messages_task: tasks.QtIntervalTask = None

        # set window constants
        self.setMinimumWidth(500)
        self.setMinimumHeight(660)
        self.setWindowTitle("hyperdome")
        self.setWindowIcon(
            QtGui.QIcon(str(resource_path / "images" / "hyperdome_logo_100.png"))
        )

        # make dialog for error messages
        self.error_window = Alert("", autostart=False)

        # initialize session variables
        self.uid: str = ""
        self.chat_history: list = []
        self.load_servers()
        self.server: Server = Server()
        self.is_connected: bool = False
        self._session: requests.Session = None
        self.crypt = encryption.LockBox()

        # Load settings, if a custom config was passed in
        self.config = config
        if self.config:
            self.settings = Settings(self.config)

        # System tray
        menu = QtWidgets.QMenu()
        self.settings_action = menu.addAction(strings._("gui_settings_window_title"))
        self.settings_action.triggered.connect(self.open_settings)
        help_action = menu.addAction(strings._("gui_settings_button_help"))
        help_action.triggered.connect(SettingsDialog.help_clicked)
        exit_action = menu.addAction(strings._("systray_menu_exit"))
        exit_action.triggered.connect(self.close)

        self.system_tray = QtWidgets.QSystemTrayIcon(self)
        self.system_tray.setIcon(
            QtGui.QIcon(str(resource_path / "images" / "hyperdome_logo_100.png"))
        )
        self.system_tray.setContextMenu(menu)
        self.system_tray.show()

        # chat pane
        self.settings_button = QtWidgets.QPushButton()
        self.settings_button.setDefault(False)
        self.settings_button.setIcon(
            QtGui.QIcon(str(resource_path / "images" / "settings_black_18dp.png"))
        )
        self.settings_button.clicked.connect(self.open_settings)

        self.message_text_field = QtWidgets.QLineEdit()
        self.message_text_field.setClearButtonEnabled(True)
        self.message_text_field.returnPressed.connect(self.send_message)
        self.message_text_field.setPlaceholderText("Enter message:")

        self.enter_button = QtWidgets.QPushButton("Send")
        self.enter_button.clicked.connect(self.send_message)

        self.enter_text = QtWidgets.QHBoxLayout()
        self.enter_text.addWidget(self.message_text_field)
        self.enter_text.addWidget(self.enter_button)
        self.enter_text.addWidget(self.settings_button)

        self.chat_window = QtWidgets.QListWidget()
        self.chat_window.setFlow(QtWidgets.QListWidget.TopToBottom)
        self.chat_window.setWrapping(False)
        self.chat_window.setVerticalScrollMode(
            QtWidgets.QAbstractItemView.ScrollPerItem
        )
        self.chat_window.addItems(self.chat_history)

        self.chat_pane = QtWidgets.QVBoxLayout()
        self.chat_pane.addWidget(self.chat_window, stretch=1)
        self.chat_pane.addLayout(self.enter_text)

        # server list view
        self.start_chat_button = QtWidgets.QPushButton()
        self.start_chat_button.setText("Start Chat")
        self.start_chat_button.setFixedWidth(100)
        self.start_chat_button.clicked.connect(self.start_chat)
        self.start_chat_button.setEnabled(False)

        self.server_dropdown = QtWidgets.QComboBox(self)
        self.server_dropdown.addItem("Select a Server")
        [self.server_dropdown.addItem(nick) for nick in self.servers]
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

        # Start the "Connecting to Tor" dialog, which calls onion.connect()
        tor_con = TorConnectionDialog(self.settings, self.qtapp, self.onion)
        tor_con.canceled.connect(self._tor_connection_canceled)
        tor_con.open_settings.connect(self._tor_connection_open_settings)
        if not self.local_only:
            tor_con.start()

    def send_message(self):
        """
        Send the contents of the message box to the server to be forwarded to
        either counsel or guest.
        """

        message = self.message_text_field.text()
        self.message_text_field.clear()

        if not (self.is_connected or self.uid):
            return self.handle_error(Exception("not in an active chat"))

        enc_message = self.crypt.encrypt_outgoing_message(message)
        send_message_task = tasks.QtTask(
            self.client.send_message, self.uid, enc_message
        )

        @tasks.run_after_task(send_message_task, error_handler=self.handle_error)
        @QtCore.pyqtSlot(object)
        def message_send_success(_):
            self.__log.debug("message sent successfully")

        self.chat_window.addItem(f"You: {message}")

    @QtCore.pyqtSlot(object)
    def on_history_added(self, messages: str):
        """
        Update UI with messages retrieved from server.
        """

        sender_name = "User" if self.server.is_counselor else "Counselor"
        message_list = [
            f"{sender_name}: {self.crypt.decrypt_incoming_message(message)}"
            for message in messages.split("\n")
            if message
        ]
        self.chat_window.addItems(message_list)

    def get_uid(self):
        """
        Ask server for a new UID for a new user session
        """
        self.stop_intervals()

        if self.server.is_counselor:
            # user is a counselor which will get uid later
            self.__log.debug("User is counselor, skipping get_uid")
            self.start_chat_button.setEnabled(True)

        else:

            @tasks.run_after_task(tasks.QtTask(self.client.get_uid), self.handle_error)
            @QtCore.pyqtSlot(object)
            def after_id(uid):
                self.__log.debug("Guest got uid successfully")
                self.uid = uid
                self.start_chat_button.setEnabled(True)

    @QtCore.pyqtSlot(Exception)
    def handle_error(self, error: Exception):
        """
        take error string and assign it to the created alert window
        changes active window with new text
        and brings to focus if currently in the background.
        """
        self.error_window.setText(error.args[0] or "no error description provided")
        self.__log.debug(f'Received "{type(error)}" from task')
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
                    "http": f"socks5h://{socks_address}:{socks_port}",
                    "https": f"socks5h://{socks_address}:{socks_port}",
                }
        return self._session

    def server_switcher(self):
        """
        Handle a switch to a different saved server by establishing a new
        connection and retrieving new UID.
        """
        self.chat_window.clear()
        self.message_text_field.clear()
        if self.is_connected:
            self.disconnect_chat()
        if self.server_dropdown.currentIndex() == self.server_dropdown.count() - 1:
            self.__log.debug("adding new server")
            self.server_dropdown.setCurrentIndex(0)
            self.start_chat_button.setEnabled(False)
            add_server_dialog = AddServerDialog(self)
            dialog_error = add_server_dialog.exec_()
            if not dialog_error:
                self.server = add_server_dialog.get_server()
                self.client = api.HyperdomeClientApi(self.server, self.session)
                self.servers[self.server.nick] = self.server
                self.server_dropdown.insertItem(1, self.server.nick)
                self.server_dropdown.setCurrentIndex(1)
                self.save_servers()
        elif self.server_dropdown.currentIndex():
            self.__log.debug("switching server")
            self.server = self.servers[self.server_dropdown.currentText()]
            self.client = api.HyperdomeClientApi(self.server, self.session)
            self.get_uid()
        else:
            self.__log.debug("switched to 'select a server'")

    def start_chat(self):

        self.start_chat_button.setEnabled(False)
        pub_key = self.crypt.public_chat_key
        if self.server.is_counselor:
            self.crypt.import_key(
                self.server.key, "123"
            )  # TODO: use private key encryption
            signature = self.crypt.sign_message(pub_key)
        else:
            signature = ""

        start_chat_task = tasks.QtTask(
            self.client.start_chat, self.uid, pub_key, signature
        )

        @tasks.run_after_task(start_chat_task, self.handle_error)
        @QtCore.pyqtSlot(object)
        def after_start(counselor):
            if not self.server.is_counselor and not counselor:
                self.__log.info("no counselors logged in to server")
                self.handle_error(Exception("No counselors available."))
                self.start_chat_button.setEnabled(True)
                return
            if self.server.is_counselor:
                self.uid = counselor
                self.__log.info("counselor got uid")

                self.poll_guest_key_task = tasks.QtIntervalTask(
                    self.client.get_guest_pub_key, self.uid, interval=5000
                )

                @tasks.run_after_task(self.poll_guest_key_task, self.handle_error)
                @QtCore.pyqtSlot(object)
                def counselor_got_guest(guest_key: str):
                    if not guest_key:
                        return
                    self.__log.info("counselor got assigned to guest")
                    self.poll_guest_key_task.stop()
                    self.crypt.perform_key_exchange(guest_key, self.server.is_counselor)
                    self.get_messages_task = tasks.QtIntervalTask(
                        self.client.get_messages, self.uid, interval=3500
                    )

                    run_on_interval = tasks.run_after_task(
                        self.get_messages_task, lambda _: self.disconnect_chat()
                    )
                    run_on_interval(self.on_history_added)

            else:
                self.crypt.perform_key_exchange(counselor, self.server.is_counselor)
                self.get_messages_task = tasks.QtIntervalTask(
                    self.client.get_messages, self.uid, interval=3500
                )

                run_on_interval = tasks.run_after_task(
                    self.get_messages_task, lambda _: self.disconnect_chat()
                )
                run_on_interval(self.on_history_added)

            self.start_chat_button.setText("Disconnect")
            self.start_chat_button.clicked.disconnect()
            self.start_chat_button.clicked.connect(self.disconnect_chat)
            self.start_chat_button.setEnabled(True)

    def _tor_connection_canceled(self):
        """
        If the user cancels before Tor finishes connecting, ask if they want to
        quit, or open settings.
        """

        def ask():
            a = Alert(
                strings._("gui_tor_connection_ask"),
                QtWidgets.QMessageBox.Question,
                buttons=QtWidgets.QMessageBox.NoButton,
                autostart=False,
            )
            settings_button = QtWidgets.QPushButton(
                strings._("gui_tor_connection_ask_open_settings")
            )
            quit_button = QtWidgets.QPushButton(
                strings._("gui_tor_connection_ask_quit")
            )
            a.addButton(settings_button, QtWidgets.QMessageBox.AcceptRole)
            a.addButton(quit_button, QtWidgets.QMessageBox.RejectRole)
            a.setDefaultButton(settings_button)
            a.exec_()

            if a.clickedButton() == settings_button:
                # Open settings
                self.__log.debug("Settings button clicked",)
                self.open_settings()

            if a.clickedButton() == quit_button:
                # Quit
                self.__log.debug("Quit button clicked")

                # Wait 1ms for the event loop to finish, then quit
                QtCore.QTimer.singleShot(1, self.qtapp.quit)

        # Wait 100ms before asking
        QtCore.QTimer.singleShot(100, ask)

    def _tor_connection_open_settings(self):
        """
        The TorConnectionDialog wants to open the Settings dialog
        """

        # Wait 1ms for the event loop to finish closing the TorConnectionDialog
        QtCore.QTimer.singleShot(1, self.open_settings)

    def open_settings(self):
        """
        Open the SettingsDialog.
        """

        def reload_settings():
            self.__log.info("settings have changed, reloading")
            self.settings.load()

            # We might've stopped the main requests timer if
            # a Tor connection failed.
            # If we've reloaded settings, we probably succeeded in obtaining
            # a new connection. If so, restart the timer.

        # TODO: Use more threadsafe dialog handling used for add_server_dialog here
        d = SettingsDialog(
            self.settings, self.onion, self.qtapp, self.config, self.local_only
        )
        d.settings_saved.connect(reload_settings)
        d.exec_()

    def stop_intervals(self):
        stop_task = self.get_messages_task or self.poll_guest_key_task or None
        if stop_task is not None:
            stop_task.stop()
            stop_task.wait(250)
            self.__log.info(f"stopped {stop_task}")
        else:
            self.__log.info("no chat to disconnect from")

    def disconnect_chat(self):
        self.start_chat_button.setEnabled(False)
        self.stop_intervals()

        @tasks.run_after_task(tasks.QtTask(self.client.counseling_complete, self.uid))
        @QtCore.pyqtSlot(object)
        def disconnected(_):
            self.__log.info("counseling completed")

        if self.server.is_counselor:

            @tasks.run_after_task(tasks.QtTask(self.client.signout_counselor, self.uid))
            @QtCore.pyqtSlot(object)
            def signed_out(_):
                self.__log.info("counselor signed out")

        self.start_chat_button.setText("Start Chat")
        self.start_chat_button.clicked.disconnect()
        self.start_chat_button_connection = self.start_chat_button.clicked.connect(
            self.start_chat
        )
        self.start_chat_button.setEnabled(True)

    def save_servers(self):
        resource_path.joinpath("servers.json").write_text(
            json.dumps(self.servers, default=lambda o: o.__dict__)
        )
        self.__log.info("servers saved to servers.json")

    def load_servers(self):
        try:
            servers_str = resource_path.joinpath("servers.json").read_text()
            servers_dict = json.loads(servers_str) if servers_str else {}
            self.servers = {key: Server(**value) for key, value in servers_dict.items()}
            self.__log.info("servers loaded from servers.json")

        except FileNotFoundError:
            self.__log.info("no existing server settings")
            self.servers = {}

    def closeEvent(self, event):
        """
        When the main window is closed, do some cleanup
        """
        self.__log.info("main window recieved closeEvent, cleaning up")
        try:
            self.disconnect_chat()
        except AttributeError:
            pass
        except Exception:
            self.__log.exception("Unexpected error during client cleanup")
        self.hide()

        # wait for any pending tasks to complete
        # allows client to signout from server gracefully
        QtCore.QThreadPool.globalInstance().waitForDone(5000)

        if self.onion:
            self.onion.cleanup()
        if self.app:
            self.app.cleanup()

        super().closeEvent(event)
        self.__log.info("hyperdome client closed")
