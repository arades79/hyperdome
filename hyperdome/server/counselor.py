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

from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PublicKey
from cryptography.exceptions import InvalidSignature
from ..common.types import key_type, bstr, arg_to_bytes


class Counselor:
    """
    container for counselors also responsible for holding keys and verifying messages
    """

    def __init__(self, name: str, pub_key: key_type):
        self.name = name
        if isinstance(pub_key, Ed448PublicKey):
            self.pub_key: Ed448PublicKey = pub_key
            return
        elif isinstance(pub_key, str):
            key_bytes: bytes = pub_key.encode('utf-8')
        else:
            key_bytes: bytes = pub_key

        self.pub_key: Ed448PublicKey = Ed448PublicKey.from_public_bytes(key_bytes)

    @arg_to_bytes
    def verify(self, signature: bstr, message: bstr) -> bool:
        try:
            self.pub_key.verify(message)
            return True
        except InvalidSignature:
            return False




