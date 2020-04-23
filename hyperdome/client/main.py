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
import logging
import signal
import sys

from PyQt5 import QtCore, QtWidgets

from ..common import strings
from ..common.common import Common, platform_str, version
from ..common.onion import Onion
from ..server.hyperdome_server import HyperdomeServer
from .hyperdome_client import HyperdomeClient


class Application(QtWidgets.QApplication):
    """
    This is Qt's QApplication class. It has been overridden to support threads
    and the quick keyboard shortcut.
    """

    logger = logging.getLogger(__name__ + ".Application")

    def __init__(self, common):
        if platform_str == "Linux" or platform_str == "BSD":
            self.setAttribute(QtCore.Qt.AA_X11InitThreads, True)
        QtWidgets.QApplication.__init__(self, sys.argv)
        self.installEventFilter(self)

    def eventFilter(self, obj, event):
        if (
            event.type() == QtCore.QEvent.KeyPress
            and event.key() == QtCore.Qt.Key_Q
            and event.modifiers() == QtCore.Qt.ControlModifier
        ):
            self.quit()
        return False


def main():
    """
    The main() function implements all of the logic that the GUI version \
    of hyperdome uses.
    """
    logger = logging.getLogger(__name__)
    common = Common()

    # Load the default settings and strings early, for the sake of
    # being able to parse options.
    # These won't be in the user's chosen locale necessarily, but
    # we need to parse them early in order to even display the option
    # to pass alternate settings (which might contain a preferred locale).
    # If an alternate --config is passed, we'll reload strings later.
    common.load_settings()
    # TODO: remove or rebuild strings
    strings.load_strings(common)

    # Allow Ctrl-C to quit the program without an exception
    # stackoverflow.com/questions/42814093/
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Start the Qt app
    qtapp = Application(common)

    # Start the Onion
    onion = Onion(common)

    # Start the hyperdome app
    app = HyperdomeServer(common, onion)

    # Launch the gui
    main_window = HyperdomeClient(common, onion, qtapp, app, None)
    main_window.show()

    # Clean up when app quits
    def shutdown():
        onion.cleanup()
        app.cleanup()

    qtapp.aboutToQuit.connect(shutdown)

    # All done
    sys.exit(qtapp.exec_())
