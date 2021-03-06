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
import shutil

import autologging

from ..common.common import get_available_port


@autologging.traced
@autologging.logged
class HyperdomeServer(object):
    """
    hyperdome is the main application class. Pass in options and run
    start_onion_service and it will do the magic.
    """

    __log: autologging.logging.Logger  # stop linter errors from autologging

    def __init__(self, onion, local_only=False):

        # The Onion object
        self.onion = onion

        self.hidserv_dir = None
        self.onion_host = None
        self._port = None

        # files and dirs to delete on shutdown
        # Note: Was originally files used for hyperdome, but we could use this
        # to ensure all traces of the program are gone from the computer
        self.cleanup_filenames = []

        # do not use tor -- for development
        self.local_only = local_only

    @property
    def port(self):
        """
        Choose a random port.
        """
        if self._port is None:
            self._port = get_available_port(17600, 17650)

        return self._port

    def start_onion_service(self):
        """
        Start the hyperdome onion service.
        """

        if self.local_only:
            self.onion_host = f"127.0.0.1:{self.port:d}"
            return

        self.onion_host = self.onion.start_onion_service(self.port)

    def cleanup(self):
        """
        Shut everything down and clean up temporary files, etc.
        """

        # Cleanup files
        try:
            for filename in self.cleanup_filenames:
                if os.path.isfile(filename):
                    os.remove(filename)
                elif os.path.isdir(filename):
                    shutil.rmtree(filename)
        except OSError:
            # Don't crash if file is still in use
            self.__log.info("file in use during cleanup")
        self.cleanup_filenames = []
