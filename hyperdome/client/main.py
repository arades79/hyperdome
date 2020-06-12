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
import signal
import sys

from PyQt5 import QtCore, QtWidgets
import autologging
import stem

from ..common import strings
from ..common.common import Settings, platform_str
from ..common.onion import Onion
from ..server.hyperdome_server import HyperdomeServer
from .hyperdome_client import HyperdomeClient


@autologging.logged
class Application(QtWidgets.QApplication):
    """
    This is Qt's QApplication class. It has been overridden to support threads
    and the quick keyboard shortcut.
    """

    def __init__(self):
        if platform_str in ["Linux", "BSD"]:
            self.setAttribute(QtCore.Qt.AA_X11InitThreads, True)
        QtWidgets.QApplication.__init__(self, sys.argv)
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if (
            event.type() == QtCore.QEvent.KeyPress
            and event.key() == QtCore.Qt.Key_Q
            and event.modifiers() == QtCore.Qt.ControlModifier
        ):
            self.__log.info("user quit through keyboard shortcut")
            self.quit()
        return False


@autologging.logged
def main():
    """
    The main() function implements all of the logic that the GUI version \
    of hyperdome uses.
    """
    settings = Settings()

    # Load the default settings and strings early, for the sake of
    # being able to parse options.
    # These won't be in the user's chosen locale necessarily, but
    # we need to parse them early in order to even display the option
    # to pass alternate settings (which might contain a preferred locale).
    # If an alternate --config is passed, we'll reload strings later.

    # TODO: remove or rebuild strings
    strings.load_strings(settings)

    # Allow Ctrl-C to quit the program without an exception
    # stackoverflow.com/questions/42814093/
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Start the Qt app
    qtapp = Application()

    # Start the Onion
    onion = Onion(settings)

    # Start the hyperdome app
    app = HyperdomeServer(onion)

    # Launch the gui
    main_window = HyperdomeClient(settings, onion, qtapp, app, None)
    main_window.show()

    # Clean up when app quits
    @qtapp.aboutToQuit.connect
    def shutdown():
        main._log.info("shutting down")
        try:
            onion.cleanup()
        except stem.SocketClosed:
            pass
        app.cleanup()

    # All done
    sys.exit(qtapp.exec_())
