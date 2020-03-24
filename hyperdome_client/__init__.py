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
import sys
import argparse
import signal
from PyQt5 import QtCore, QtWidgets

from hyperdome_server import strings
from hyperdome_server.common import Common
from hyperdome_server.onion import Onion
from hyperdome_server.hyperdome_server import HyperdomeServer

from .hyperdome_client import HyperdomeClient


class Application(QtWidgets.QApplication):
    """
    This is Qt's QApplication class. It has been overridden to support threads
    and the quick keyboard shortcut.
    """

    def __init__(self, common):
        if common.platform == "Linux" or common.platform == "BSD":
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
    of onionshare uses.
    """
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

    # Display OnionShare banner
    print(strings._("version_string").format(common.version))

    # Allow Ctrl-C to quit the program without an exception
    # stackoverflow.com/questions/42814093/
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # Start the Qt app
    qtapp = Application(common)

    # Parse arguments
    parser = argparse.ArgumentParser(
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=48)
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        dest="local_only",
        help=strings._("help_local_only"),
    )
    parser.add_argument(
        "--debug", action="store_true", dest="debug", help=strings._("help_debug")
    )
    parser.add_argument(
        # TODO: default should be empty string for consistant typing
        "--config", metavar="config", default=False, help=strings._("help_config")
    )
    args = parser.parse_args()

    config = args.config
    if config:
        # Re-load the strings, in case the provided config has changed locale
        common.load_settings(config)
        strings.load_strings(common)

    local_only = bool(args.local_only)
    common.debug = bool(args.debug)

    # Start the Onion
    onion = Onion(common)

    # Start the OnionShare app
    app = HyperdomeServer(common, onion, local_only)

    # Launch the gui
    HyperdomeClient(common, onion, qtapp, app, None, config, local_only)

    # Clean up when app quits
    def shutdown():
        onion.cleanup()
        app.cleanup()

    qtapp.aboutToQuit.connect(shutdown)

    # All done
    sys.exit(qtapp.exec_())


if __name__ == "__main__":
    main()
