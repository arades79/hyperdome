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
import os
import shutil

from ..common.common import ShutdownTimer, get_available_port


class HyperdomeServer(object):
    """
    hyperdome is the main application class. Pass in options and run
    start_onion_service and it will do the magic.
    """

    logger = logging.getLogger(__name__)

    def __init__(self, common, onion, local_only=False, shutdown_timeout=0):
        self.common = common

        self.logger.debug("__init__")

        # The Onion object
        self.onion = onion

        self.hidserv_dir = None
        self.onion_host = None
        self.port = None

        # files and dirs to delete on shutdown
        # Note: Was originally files used for hyperdome, but we could use this
        # to ensure all traces of the program are gone from the computer
        self.cleanup_filenames = []

        # do not use tor -- for development
        self.local_only = local_only

        # optionally shut down after N hours
        self.shutdown_timeout = shutdown_timeout
        # init timing thread
        self.shutdown_timer = None

    def choose_port(self):
        """
        Choose a random port.
        """
        self.port = get_available_port(17600, 17650)

    def start_onion_service(self):
        """
        Start the hyperdome onion service.
        """
        self.logger.debug("start_onion_service")

        if not self.port:
            self.choose_port()

        if self.shutdown_timeout > 0:
            self.shutdown_timer = ShutdownTimer(self.common, self.shutdown_timeout)

        if self.local_only:
            self.onion_host = "127.0.0.1:{0:d}".format(self.port)
            return

        self.onion_host = self.onion.start_onion_service(self.port)

    def cleanup(self):
        """
        Shut everything down and clean up temporary files, etc.
        """
        self.logger.debug("cleanup")

        # Cleanup files
        try:
            for filename in self.cleanup_filenames:
                if os.path.isfile(filename):
                    os.remove(filename)
                elif os.path.isdir(filename):
                    shutil.rmtree(filename)
        except OSError:
            # Don't crash if file is still in use
            self.logger.info("file in use during cleanup")
            pass
        self.cleanup_filenames = []
