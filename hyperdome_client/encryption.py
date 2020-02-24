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
import typing
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
import cryptography.hazmat.primitives.serialization as serial
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from cryptography.fernet import Fernet

bstr = typing.Union[str, bytes]


class LockBox():
    """
    handle key storage, generation, exchange,
    encryption and decryption
    """

    _chat_key = None
    _signing_key = None
    _shared_secret = None
    _HASH = hashes.SHA3_256()
    _ENCODING = serial.Encoding.PEM
    _BACKEND = default_backend()
    _PUBLIC_FORMAT = serial.PublicFormat.SubjectPublicKeyInfo
    _PRIVATE_FORMAT = serial.PrivateFormat.PKCS8

    def __init__(self):
        # TODO consider ephemeral/rotating keys
        self.rotate()

    @property
    def public_chat_key(self) -> bytes:
        """
        return a PEM encoded serialized public key digest
        of the current private X25519 chat key
        """
        key = self._chat_key.public_key()
        key_bytes = key.public_bytes(
            self._ENCODING, self._PUBLIC_FORMAT)
        return key_bytes

    @property
    def public_signing_key(self) -> bytes:
        """
        return a PEM encoded serialized public key digest
        of the current private Ed25519 signing key
        """
        key = self._signing_key.public_key()
        key_bytes = key.public_bytes(
            self._ENCODING, self._PUBLIC_FORMAT)
        return key_bytes

    def make_shared_secret(self, public_key_bytes: bstr):
        """
        ingest a PEM encoded public key and generate a symmetric key
        created by a Diffie-Helman key exchange result being passed into
        a key-derivation and used to create a fernet instance
        """
        if isinstance(public_key_bytes, str):
            public_key_bytes = public_key_bytes.encode()
        public_key = serial.load_pem_public_key(public_key_bytes, self._BACKEND)
        shared = self._chat_key.exchange(public_key)
        key_gen = HKDF(algorithm=self._HASH, length=16,
                       salt=None, info=b'handshake', backend=self._BACKEND)
        # TODO consider customizing symmetric encryption for larger key or authentication
        self._shared_secret = Fernet(key_gen.derive(shared))

    def encrypt_message(self, message: bstr) -> bytes:
        if isinstance(message, str):
            message = message.encode()
        return self._shared_secret.encrypt(message)

    def decrypt_message(self, message: bstr) -> str:
        if isinstance(message, str):
            message = message.encode()
        return self._shared_secret.decrypt(message).decode('utf-8')

    def make_signing_key(self):
        self._signing_key = Ed25519PrivateKey.generate()

    def sign_message(self, message: bstr) -> bytes:
        if isinstance(message, str):
            message = message.encode()
        sig = self._signing_key.sign(message)
        return sig

    def rotate(self):
        """
        set a new key pair and invalidate the current shared secret
        """
        self._chat_key = X25519PrivateKey.generate()
        self._shared_secret = None

    def save_key(self, identifier, passphrase):
        filename = f".{identifier}.pem"
        with open(filename, 'wb') as file:
            file.write(
                self._signing_key.private_bytes(
                    self._ENCODING,
                    self._PRIVATE_FORMAT,
                    serial.BestAvailableEncryption(passphrase)))

    def load_key(self, identifier, passphrase):
        filename = f".{identifier}.pem"
        with open(filename, 'rb') as file:
            enc_key = file.read()
            self._signing_key = serial.load_pem_private_key(enc_key, passphrase, self._BACKEND)
