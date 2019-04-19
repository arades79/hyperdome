# -*- coding: utf-8 -*-
"""
OnionShare | https://onionshare.org/

Copyright (C) 2014-2018 Micah Lee <micah@micahflee.com>

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
import queue
from PyQt5 import QtCore, QtWidgets, QtGui

from onionshare import strings
from onionshare.web import Web

from .mode.share_mode import ShareMode
from .mode.receive_mode import ReceiveMode

from .tor_connection_dialog import TorConnectionDialog
from .settings_dialog import SettingsDialog
from .widgets import Alert
from .update_checker import UpdateThread
from .server_status import ServerStatus
from .add_server_dialog import AddServerDialog

import requests


session = requests.Session()
# session.proxies = {'http': 'socks5://127.0.0.1:9050',
#                    'https': 'socks5://127.0.0.1:9050'}

class Server(object):
    def __init__(self, url='', uname='', passwd='', is_therapist=False):
        self.url = url
        self.username = uname
        self.password = passwd
        self.is_therapist = is_therapist


class OnionShareGui(QtWidgets.QMainWindow):
    """
    OnionShareGui is the main window for the GUI that contains all of the
    GUI elements.
    """

    def __init__(self, common, onion, qtapp, app, filenames, config=False, local_only=False):
        super(OnionShareGui, self).__init__()

        self.common = common
        self.common.log('OnionShareGui', '__init__')
        self.setMinimumWidth(500)
        self.setMinimumHeight(660)
        self.uid = ''
        self.chat_history = []
        self.servers = dict()
        self.server = Server()
        self.is_connected = False

        self.onion = onion
        self.qtapp = qtapp
        self.app = app
        self.local_only = local_only

        self.setWindowTitle('hyperdome')
        self.setWindowIcon(QtGui.QIcon(self.common.get_resource_path('images/logo.png')))

        # Load settings, if a custom config was passed in
        self.config = config
        if self.config:
            self.common.load_settings(self.config)

        # Server status indicator on the status bar
        self.server_status_image_stopped = QtGui.QImage(self.common.get_resource_path('images/server_stopped.png'))
        self.server_status_image_working = QtGui.QImage(self.common.get_resource_path('images/server_working.png'))
        self.server_status_image_started = QtGui.QImage(self.common.get_resource_path('images/server_started.png'))
        self.server_status_image_label = QtWidgets.QLabel()
        self.server_status_image_label.setFixedWidth(20)
        self.server_status_label = QtWidgets.QLabel('')
        self.server_status_label.setStyleSheet(self.common.css['server_status_indicator_label'])
        server_status_indicator_layout = QtWidgets.QHBoxLayout()
        server_status_indicator_layout.addWidget(self.server_status_image_label)
        server_status_indicator_layout.addWidget(self.server_status_label)
        self.server_status_indicator = QtWidgets.QWidget()
        self.server_status_indicator.setLayout(server_status_indicator_layout)

        # Status bar
        self.status_bar = QtWidgets.QStatusBar()
        self.status_bar.setSizeGripEnabled(False)
        self.status_bar.setStyleSheet(self.common.css['status_bar'])
        self.status_bar.addPermanentWidget(self.server_status_indicator)
        self.setStatusBar(self.status_bar)

        # System tray
        menu = QtWidgets.QMenu()
        self.settings_action = menu.addAction(strings._('gui_settings_window_title'))
        self.settings_action.triggered.connect(self.open_settings)
        help_action = menu.addAction(strings._('gui_settings_button_help'))
        help_action.triggered.connect(SettingsDialog.help_clicked)
        exit_action = menu.addAction(strings._('systray_menu_exit'))
        exit_action.triggered.connect(self.close)

        self.system_tray = QtWidgets.QSystemTrayIcon(self)
        # The convention is Mac systray icons are always grayscale
        if self.common.platform == 'Darwin':
            self.system_tray.setIcon(QtGui.QIcon(self.common.get_resource_path('images/logo_grayscale.png')))
        else:
            self.system_tray.setIcon(QtGui.QIcon(self.common.get_resource_path('images/logo.png')))
        self.system_tray.setContextMenu(menu)
        self.system_tray.show()

        self.server_add_dialog = AddServerDialog(common=self.common, add_server_action=self.add_server)


        # chat pane
        self.settings_button = QtWidgets.QPushButton()
        self.settings_button.setDefault(False)
        self.settings_button.setFixedWidth(40)
        self.settings_button.setFixedHeight(50)
        self.settings_button.setIcon( QtGui.QIcon(self.common.get_resource_path('images/settings.png')) )
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
        self.server_dialog_button = QtWidgets.QPushButton()
        self.server_dialog_button.setText('Add New Server')
        self.server_dialog_button.setFixedWidth(100)
        self.server_dialog_button.clicked.connect(self.server_add_dialog.exec_)

        self.server_dropdown = QtWidgets.QComboBox()
        self.server_dropdown.currentIndexChanged.connect(lambda i:self.server_switcher(self.server_dropdown.currentText()))

        self.server_pane = QtWidgets.QHBoxLayout()
        self.server_pane.addWidget(self.server_dropdown)
        self.server_pane.addWidget(self.server_dialog_button)


        # full view
        self.full_layout = QtWidgets.QVBoxLayout()
        self.full_layout.addLayout(self.server_pane)
        self.full_layout.addLayout(self.chat_pane)
        # self.setLayout(self.full_layout)

        self.main_widget = QtWidgets.QWidget()
        self.main_widget.setLayout(self.full_layout)

        self.setCentralWidget(self.main_widget)
        self.show()

        # Create the timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.timer_callback)

        # Start the "Connecting to Tor" dialog, which calls onion.connect()
        tor_con = TorConnectionDialog(self.common, self.qtapp, self.onion)
        tor_con.canceled.connect(self._tor_connection_canceled)
        tor_con.open_settings.connect(self._tor_connection_open_settings)
        if not self.local_only:
            tor_con.start()

        self.timer.start(1000)

    def send_message(self):
        if self.is_connected:
            message = self.message_text_field.toPlainText()
            self.message_text_field.clear()
            try:
                if not (self.uid or self.server.is_therapist):
                    self.get_uid()
                self.chat_history.append("You: " + message)
                self.on_history_added()
                if self.server.is_therapist: # needs auth
                    session.post(f"{self.server.url}/message_from_therapist",headers={"username":self.server.username, "password":self.server.password,"message":message})
                else: # normal user
                    session.post(self.server.url + '/message_from_user', data = {'message':message, 'guest_id':self.uid} )
            except Exception as e:
                print(e.with_traceback())
                Alert(self.common, "therapy machine broke", QtWidgets.QMessageBox.Warning, buttons=QtWidgets.QMessageBox.Ok)
        else:
            Alert(self.common, "Not connected to a counselor!", QtWidgets.QMessageBox.Warning, buttons=QtWidgets.QMessageBox.Ok)

    def on_history_added(self):
        self.chat_window.addItems(self.chat_history)
        self.chat_history = []

    def get_uid(self):
        self.uid = session.get(self.server.url + '/generate_guest_id').text


    def server_switcher(self, server):
        self.server = self.servers[server]
        self.chat_window.clear()
        self.message_text_field.clear()
        try:
            if self.server.is_therapist:
                session.post(f"{self.server.url}/therapist_signup", data={"masterkey":"megumin","username":self.server.username,"password":self.server.password})
            else:
                self.get_uid()
                self.therapist = session.post(f"{self.server.url}/request_therapist",  data={"guest_id":self.uid}).text
                if self.therapist:
                    self.is_connected = True
        except:
            Alert(self.common, "therapy machine broke", QtWidgets.QMessageBox.Warning, buttons=QtWidgets.QMessageBox.Ok)


    def add_server(self, url, nick, uname, passwd, is_therapist):
        self.server = Server(url, uname, passwd, is_therapist)
        self.servers[nick] = self.server
        self.server.is_therapist = is_therapist
        try:
            if self.server.is_therapist:
                pass
                #TODO: authenticate the therapist here when that's a thing
            else:
                session.get(url + '/generate_guest_id').text
            self.server_dropdown.addItem(nick)
            self.server_add_dialog.close()
        except Exception as e:
            print(e.with_traceback())
            Alert(self.common, f"server {url} is invalid", QtWidgets.QMessageBox.Warning, buttons=QtWidgets.QMessageBox.Ok)
            


    def _tor_connection_canceled(self):
        """
        If the user cancels before Tor finishes connecting, ask if they want to
        quit, or open settings.
        """
        self.common.log('OnionShareGui', '_tor_connection_canceled')

        def ask():
            a = Alert(self.common, strings._('gui_tor_connection_ask'), QtWidgets.QMessageBox.Question, buttons=QtWidgets.QMessageBox.NoButton, autostart=False)
            settings_button = QtWidgets.QPushButton(strings._('gui_tor_connection_ask_open_settings'))
            quit_button = QtWidgets.QPushButton(strings._('gui_tor_connection_ask_quit'))
            a.addButton(settings_button, QtWidgets.QMessageBox.AcceptRole)
            a.addButton(quit_button, QtWidgets.QMessageBox.RejectRole)
            a.setDefaultButton(settings_button)
            a.exec_()

            if a.clickedButton() == settings_button:
                # Open settings
                self.common.log('OnionShareGui', '_tor_connection_canceled', 'Settings button clicked')
                self.open_settings()

            if a.clickedButton() == quit_button:
                # Quit
                self.common.log('OnionShareGui', '_tor_connection_canceled', 'Quit button clicked')

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
            self.common.log('OnionShareGui', 'open_settings', 'settings have changed, reloading')
            self.common.settings.load()

            # We might've stopped the main requests timer if a Tor connection failed.
            # If we've reloaded settings, we probably succeeded in obtaining a new
            # connection. If so, restart the timer.
            if not self.local_only:
                if self.onion.is_authenticated():
                    if not self.timer.isActive():
                        self.timer.start(500)
                    self.share_mode.on_reload_settings()
                    self.receive_mode.on_reload_settings()
                    self.status_bar.clearMessage()

            # If we switched off the shutdown timeout setting, ensure the widget is hidden.
            if not self.common.settings.get('shutdown_timeout'):
                self.share_mode.server_status.shutdown_timeout_container.hide()
                self.receive_mode.server_status.shutdown_timeout_container.hide()

        d = SettingsDialog(self.common, self.onion, self.qtapp, self.config, self.local_only)
        d.settings_saved.connect(reload_settings)
        d.exec_()

        # When settings close, refresh the server status UI
        # self.share_mode.server_status.update()
        # self.receive_mode.server_status.update()

    def check_for_updates(self):
        """
        Check for updates in a new thread, if enabled.
        """
        if self.common.platform == 'Windows' or self.common.platform == 'Darwin':
            if self.common.settings.get('use_autoupdate'):
                def update_available(update_url, installed_version, latest_version):
                    Alert(self.common, strings._("update_available").format(update_url, installed_version, latest_version))

                self.update_thread = UpdateThread(self.common, self.onion, self.config)
                self.update_thread.update_available.connect(update_available)
                self.update_thread.start()

    def timer_callback(self):
        # Collecting messages as a user:

        if self.server == None:
            self.timer.start(1000)
            return
        if self.server.is_therapist:
            new_messages = session.get(f"{self.server.url}/collect_therapist_messages",
                                       headers={"username":self.server.username, "password":self.server.password}).text
            if new_messages: 
                new_messages = new_messages.split('\n')
                for message in new_messages:
                    message = 'Guest: ' + message   
                self.chat_window.addItems(new_messages)
        elif self.uid:
            new_messages = session.get(f"{self.server.url}/collect_guest_messages", data={"guest_id":self.uid}).text
            if new_messages:
                new_messages = new_messages.split('\n')
                for message in new_messages:
                    message = self.therapist+ ': ' + message
                self.chat_window.addItems(new_messages)
        
        self.timer.start(1000)


    def copy_url(self):
        """
        When the URL gets copied to the clipboard, display this in the status bar.
        """
        self.common.log('OnionShareGui', 'copy_url')
        self.system_tray.showMessage(strings._('gui_copied_url_title'), strings._('gui_copied_url'))

    def copy_hidservauth(self):
        """
        When the stealth onion service HidServAuth gets copied to the clipboard, display this in the status bar.
        """
        self.common.log('OnionShareGui', 'copy_hidservauth')
        self.system_tray.showMessage(strings._('gui_copied_hidservauth_title'), strings._('gui_copied_hidservauth'))



    def closeEvent(self, e):
        self.common.log('OnionShareGui', 'closeEvent')
        try:
            if self.server.is_therapist:
                session.post(f"{self.server.url}/therapist_signout",data={"username":self.server.username, "password":self.server.password})
            if server_status.status != server_status.STATUS_STOPPED:
                self.common.log('OnionShareGui', 'closeEvent, opening warning dialog')
                dialog = QtWidgets.QMessageBox()
                dialog.setWindowTitle(strings._('gui_quit_title'))
                if self.mode == OnionShareGui.MODE_SHARE:
                    dialog.setText(strings._('gui_share_quit_warning'))
                else:
                    dialog.setText(strings._('gui_receive_quit_warning'))
                dialog.setIcon(QtWidgets.QMessageBox.Critical)
                quit_button = dialog.addButton(strings._('gui_quit_warning_quit'), QtWidgets.QMessageBox.YesRole)
                dont_quit_button = dialog.addButton(strings._('gui_quit_warning_dont_quit'), QtWidgets.QMessageBox.NoRole)
                dialog.setDefaultButton(dont_quit_button)
                reply = dialog.exec_()

                # Quit
                if reply == 0:
                    self.stop_server()
                    e.accept()
                # Don't Quit
                else:
                    e.ignore()

        except:
            e.accept()
