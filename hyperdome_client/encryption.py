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

# considering using pyca/cryptography instead
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.fernet import Fernet

class LockBox():
    """
    handle key storage, encryption and decryption
    """

    def __init__(self):
        # TODO consider ephemeral/rotating keys
        self._private_key = ec.generate_private_key(ec.SECP521R1(), default_backend())
        self._shared_secret = None

    def get_public_key(self):
        self._private_key.public_key()

    def make_shared_secret(self, public_key):
        shared = self._private_key.exchange(ec.ECDH(), public_key)
        key_gen = HKDF(algorithm=hashes.SHA3_512(), length=32, salt=None, info=b'handshake', backend=default_backend())
        self._shared_secret = Fernet(key_gen.derive(shared))

    def encrypt_message(self, message):
        return self._shared_secret.encrypt(message)

    def decrypt_message(self, message):
        return self._shared_secret.decrypt(message)

