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

import autologging
import os
import sys
import threading
import time

from ..common import strings
from ..common.common import Settings, platform_str
from ..common.onion import Onion, TorErrorProtocolError, TorTooOld
from .hyperdome_server import HyperdomeServer
from .web import Web


@autologging.traced
@autologging.logged
def main(cwd=""):
    """
    The main() function implements all of the logic that the command-line
    version of hyperdome uses.
    """
    # Load the default settings and strings early, for the sake of being able
    # to parse options.
    # These won't be in the user's chosen locale necessarily, but we need to
    # parse them early in order to even display the option to pass alternate
    # settings (which might contain a preferred locale).
    # If an alternate --config is passed, we'll reload strings later.
    settings = Settings()
    strings.load_strings(settings)

    # hyperdome in OSX needs to change current working directory (onionshare #132)
    if platform_str == "Darwin" and cwd:
        os.chdir(cwd)

    # Create the Web object
    web = Web()

    # Start the Onion object
    onion = Onion(settings)
    try:
        onion.connect(
            # TODO: onion should get these values from elsewhere as new CLI has moved where the values are coming from
        )
    except KeyboardInterrupt:
        main._log.info("keyboard interrupt during onion setup")
        sys.exit()
    except Exception as e:
        sys.exit(e.args[0])

    # Start the hyperdome server
    try:
        app = HyperdomeServer(onion, False)
        app.start_onion_service()
    except KeyboardInterrupt:
        main._log.info("keyboard interrupt during onion setup, exiting")
        sys.exit()
    except (TorTooOld, TorErrorProtocolError) as e:
        main._log.exception("Tor incompatible")
        sys.exit()

    # Start hyperdome http service in new thread
    t = threading.Thread(target=web.start, args=(app.port, True))
    t.daemon = True
    t.start()

    try:  # Trap Ctrl-C
        # TODO this looks dangerously like a race condition
        # Wait for web.generate_slug() to finish running
        time.sleep(0.2)

        print(
            f"{strings._('give_this_url')}\n"
            f"http://{app.onion_host}\n"
            f"{strings._('ctrlc_to_stop')}"
        )

        while t.is_alive():
            time.sleep(1)

    except KeyboardInterrupt:
        main._log.info("application stopped from keyboard interrupt")
        web.stop(app.port)
    except TimeoutError:
        main._log.info("application stopped from timer expiration")
        web.stop(app.port)
    finally:
        main._log.debug("shutdown")
        # Shutdown
        app.cleanup()
        onion.cleanup()
