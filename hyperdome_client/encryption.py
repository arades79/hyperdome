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
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.fernet import Fernet

bstr = typing.Union[str, bytes]


class LockBox():
    """
    handle key storage, generation, exchange,
    encryption and decryption
    """

    _private_key = None
    _shared_secret = None

    def __init__(self):
        # TODO consider ephemeral/rotating keys
        self.rotate()

    @property
    def public_key(self) -> bytes:
        """
        return a PEM encoded serialized public key digest
        of the current private key
        """
        key = self._private_key.public_key()
        key_bytes = key.public_bytes(
            serial.Encoding.PEM, serial.PublicFormat.SubjectPublicKeyInfo)
        return key_bytes

    def make_shared_secret(self, public_key_bytes: bstr):
        """
        ingest a PEM encoded public key and generate a symmetric key
        created by a Diffie-Helman key exchange result being passed into
        a key-derivation and used to create a fernet instance
        """
        if isinstance(public_key_bytes, str):
            public_key_bytes = public_key_bytes.encode()
        public_key = serial.load_pem_public_key(public_key_bytes, default_backend())
        shared = self._private_key.exchange(ec.ECDH(), public_key)
        key_gen = HKDF(algorithm=hashes.SHA3_256(), length=16,
                       salt=None, info=b'handshake', backend=default_backend())
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

    def sign_message(self, message: bstr) -> bytes:
        if isinstance(message, str):
            message = message.encode()
        sig = self._private_key.sign(
            message,
            ec.ECDSA(hashes.SHA3_256()))
        return sig

    def rotate(self):
        """
        set a new key pair and invalidate the current shared secret
        """
        self._private_key = ec.generate_private_key(
            ec.SECP521R1(), default_backend())
        self._shared_secret = None

    def save_key(self, identifier, passphrase):
        filename = f".{identifier}.pem"
        with open(filename, 'wb') as file:
            file.write(
                self._private_key.private_bytes(
                    serial.Encoding.PEM,
                    serial.PrivateFormat.PKCS8,
                    serial.BestAvailableEncryption(passphrase)))

    def load_key(self, identifier, passphrase):
        filename = f".{identifier}.pem"
        with open(filename, 'rb') as file:
            enc_key = file.read()
            self._private_key = serial.load_pem_private_key(enc_key, passphrase, default_backend())
