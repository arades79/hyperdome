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
import Crypto.Cipher.AES as Sym_enc
import Crypto.PublicKey.ECC as Asym_enc
import Crypto.Random as Rand

import cryptography.fernet

class LockBox():
    """
    handle key storage, encryption and decryption
    """

    def __init__(self):
        self._key = Asym_enc.generate()
        # TODO hard coded key is for testing ONLY
        self._partial_secret = b'Lx\x84!PMo\x0c\xc8\x88\xb0\xae\xba\x1f\xb5\x8a'
        self.chat_encryption = None

    def dec_secret(self, message):
        if self.chat_encryption == None:
            return

        return self.chat_encryption.decrypt(message)

    def enc_secret(self, message):
        if self.chat_encryption == None:
            return

        return self.chat_encryption.encrypt(message)

    def make_shared_secret(self, incoming_partial):
        secret = self._partial_secret + incoming_partial
        self.chat_encryption = Sym_enc.new(secret,Sym_enc.MODE_GCM)

    @property
    def pubkey(self):
        return self._key.public_key()

