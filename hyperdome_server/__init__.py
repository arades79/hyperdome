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

import os
import sys
import time
import argparse
import threading

from . import strings
from .common import Common
from .web import Web
from .onion import TorErrorProtocolError, TorTooOld, Onion
from .hyperdome_server import HyperdomeServer


def main(cwd=None):
    """
    The main() function implements all of the logic that the command-line
    version of hyperdome uses.
    """
    common = Common()

    # Load the default settings and strings early, for the sake of being able
    # to parse options.
    # These won't be in the user's chosen locale necessarily, but we need to
    # parse them early in order to even display the option to pass alternate
    # settings (which might contain a preferred locale).
    # If an alternate --config is passed, we'll reload strings later.
    common.load_settings()
    strings.load_strings(common)

    # Display Hyperdome banner
    print(f"Hyperdome Server {common.version}")

    # hyperdome in OSX needs to change current working directory (Onionshare #132)
    if common.platform == "Darwin" and cwd:
        os.chdir(cwd)

    # Create the Web object
    web = Web(common, False)

    # Start the Onion object
    onion = Onion(common)
    try:
        onion.connect(
            custom_settings=False, config='', connect_timeout=0
            # TODO: onion should get these values from elsewhere as new CLI has moved where the values are coming from
        )
    except KeyboardInterrupt:
        print("")
        sys.exit()
    except Exception as e:
        sys.exit(e.args[0])

    # Start the hyperdome server
    try:
        app = HyperdomeServer(common, onion, local_only, shutdown_timeout)
        app.choose_port()
        app.start_onion_service()
    except KeyboardInterrupt:
        print("")
        sys.exit()
    except (TorTooOld, TorErrorProtocolError) as e:
        print("")
        print(e.args[0])
        sys.exit()

    # Start hyperdome http service in new thread
    t = threading.Thread(target=web.start, args=(app.port, True))
    t.daemon = True
    t.start()

    try:  # Trap Ctrl-C
        # TODO this looks dangerously like a race condition
        # Wait for web.generate_slug() to finish running
        time.sleep(0.2)

        # start shutdown timer thread
        if app.shutdown_timeout > 0:
            app.shutdown_timer.start()

        print("")
        url = f"http://{app.onion_host}"
        print(strings._("give_this_url"))
        print("Do not copy the slug (part after last /) for now")
        print(url)
        print()
        print(strings._("ctrlc_to_stop"))

        # Wait for app to close
        while t.is_alive():
            if app.shutdown_timeout > 0:
                # if the shutdown timer was set and has run out, stop the
                # server
                if not app.shutdown_timer.is_alive():
                    pass
                    # TODO if hyperdome session is over, break. Or just add
                    # to the conditions with app.shutdown_timer.is_alive().
            # Allow KeyboardInterrupt exception to be handled with threads
            # https://stackoverflow.com/questions/3788208
            time.sleep(0.2)
    except KeyboardInterrupt:
        web.stop(app.port)
    finally:
        # Shutdown
        app.cleanup()
        onion.cleanup()


if __name__ == "__main__":
    main()
