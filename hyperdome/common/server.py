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
import logging


class Server:
    """
    Holder class for server connection details
    """

    logger = logging.getLogger(__name__)

    class InvalidOnionAddress(Exception):
        """
        The onion address provided does not contain a valid v3 public key
        """

        pass

    def __init__(
        self,
        url: str = "",
        nick: str = "",
        username: str = "",
        key: str = "",
        is_counselor=False,
    ):
        self.url = url.strip()
        if url:
            self._check_url()
        self.nick = nick
        self.username = username
        self.key = key
        self.is_counselor = is_counselor

    def _check_url(self):
        """
        Ensure URL is properly formatted
        """

        if not (self.url.startswith(("http://", "https://"))):
            # tor hidden services do not support https so http default is okay
            self.url = f"http://{self.url}"
        if not self.url.endswith(".onion"):
            self.url = f"{self.url}.onion"

        onion_key = self.url[7:-6]
        key_len = len(onion_key)
        last_char = onion_key[-1]
        self.logger.debug(f"onion url check: {key_len=} {last_char=}")

        if key_len != 56 or last_char != "d":
            bad_len = f"bad length, {key_len=} instead of 56 " if key_len != 56 else ""
            wrong_pad = (
                f"wrong padding, {last_char=} instead of d" if last_char != "d" else ""
            )
            raise self.InvalidOnionAddress(f"key had {bad_len}{wrong_pad}")
