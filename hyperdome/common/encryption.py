# -*- coding: utf-8 -*-
"""
Hyperdome

Copyright (C) 2019-2020 Skyelar Craver <scravers@protonmail.com>
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
import base64
import functools
import secrets
from typing import Iterable

import autologging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
import cryptography.hazmat.primitives.serialization as serial


def generate_one_time_keys() -> dict[X25519PublicKey, X25519PrivateKey]:
    key_map = dict()
    for _ in range(100):
        key = X25519PrivateKey.generate()
        key_map[key.public_key()] = key
    return key_map


def sign_key(signing_key: Ed25519PrivateKey, public_key: X25519PublicKey):
    key_bytes = public_key.public_bytes(serial.Encoding.Raw, serial.PublicFormat.Raw)
    return signing_key.sign(key_bytes)


def sign_key_pack(
    signing_key: Ed25519PrivateKey, public_keys: Iterable[X25519PublicKey]
):
    key_bytes = b""
    for key in public_keys:
        key_bytes += key.public_bytes(serial.Encoding.Raw, serial.PublicFormat.Raw)
    return signing_key.sign(key_bytes)


def generate_signed_key_bundle(signing_key: Ed25519PrivateKey):
    pre_key = X25519PrivateKey.generate()
    pre_key_signature = sign_key(signing_key, pre_key.public_key())
    otk_pack = generate_one_time_keys()
    otk_pack_signature = sign_key_pack(signing_key, otk_pack.keys())


key_derivation_function = HKDF(
    hashes.BLAKE2b(64), 64, b"hyperdome", b"ratchet increment", default_backend()
)
ALGORITHM = (
    f"Ed25519+X25519+HKDF-{key_derivation_function._algorithm.name}-ChaCha20Poly1305"
)
VERSION = "v1"


class KeyRatchet:
    """
    automatically ratcheting cipher
    """

    def __init__(self, initial_key_material: bytes):
        if len(initial_key_material) != 32:
            raise ValueError("initial key material must be 32 bytes")
        self._kdf_key = initial_key_material
        self._increment()
        self._counter: int = 0

    def _increment(self):
        new_key_bytes = key_derivation_function.derive(self._kdf_key)
        self._kdf_key = new_key_bytes[32:]
        self._enc_key = ChaCha20Poly1305(new_key_bytes[:32])
        self._counter += 1


class SendKeyRatchet(KeyRatchet):
    def __init__(self, initial_key_material: bytes):
        super().__init__(initial_key_material)

    def encrypt(
        self, plaintext: bytes, additional_data: bytes | None = None
    ) -> dict[str, bytes | int]:
        nonce = secrets.token_bytes(12)
        ciphertext = self._enc_key.encrypt(nonce, plaintext, additional_data)
        message = {
            "nonce": nonce,
            "sequence": self._counter,
            "ciphertext": ciphertext,
        }
        self._increment()
        return message


class RecieveKeyRatchet(KeyRatchet):
    def __init__(self, initial_key_material: bytes):
        super().__init__(initial_key_material)
        self._run_ahead_buffer: dict[int, ChaCha20Poly1305] = dict()

    def _run_ahead(self, iterations: int):
        for _ in range(iterations):
            self._run_ahead_buffer[self._counter] = self._enc_key
            self._increment()

    def decrypt(
        self,
        nonce: bytes,
        sequence: int,
        ciphertext: bytes,
        associated_data: bytes | None = None,
    ) -> bytes:
        if sequence > self._counter:
            self._run_ahead(sequence - self._counter)

        if sequence == self._counter:
            key = self._enc_key
        elif sequence in self._run_ahead_buffer.keys():
            key = self._run_ahead_buffer.pop(sequence)
        else:
            raise ValueError("impossible to decrypt message with given sequence")

        plaintext = key.decrypt(nonce, ciphertext, associated_data)
        return plaintext


def half_authenticated_double_dh_exchange(
    csp_key: X25519PrivateKey | X25519PublicKey,
    eph_key: X25519PublicKey | X25519PrivateKey,
    ot_key: X25519PrivateKey | X25519PublicKey,
    cid_key: Ed25519PublicKey | None = None,
    csp_sig: bytes | None = None,
) -> tuple[SendKeyRatchet, RecieveKeyRatchet]:
    if (
        cid_key is None
        and csp_sig is None
        and isinstance(csp_key, X25519PrivateKey)
        and isinstance(eph_key, X25519PublicKey)
        and isinstance(ot_key, X25519PrivateKey)
    ):
        dh1 = csp_key.exchange(eph_key)
        dh2 = ot_key.exchange(eph_key)
        send_slice = slice(None, 32)
        recv_slice = slice(32, None)
    elif (
        isinstance(cid_key, Ed25519PublicKey)
        and isinstance(csp_sig, bytes)
        and isinstance(eph_key, X25519PrivateKey)
        and isinstance(csp_key, X25519PublicKey)
        and isinstance(ot_key, X25519PublicKey)
    ):
        cid_key.verify(
            csp_sig, csp_key.public_bytes(serial.Encoding.Raw, serial.PublicFormat.Raw)
        )
        dh1 = eph_key.exchange(csp_key)
        dh2 = eph_key.exchange(ot_key)
        send_slice = slice(32, None)
        recv_slice = slice(None, 32)
    else:
        raise TypeError("public/private key mismatch")
    shared_secret = key_derivation_function.derive(dh1 + dh2)
    send_ratchet = SendKeyRatchet(shared_secret[send_slice])
    recv_ratchet = RecieveKeyRatchet(shared_secret[recv_slice])
    return (send_ratchet, recv_ratchet)


@autologging.traced
@autologging.logged
class LockBox:
    """
    handle key storage, generation, exchange,
    encryption and decryption
    """

    _chat_key: X25519PrivateKey
    _signing_key: Ed25519PrivateKey
    _send_ratchet_key: bytes = b""
    _recieve_ratchet_key: bytes = b""
    _HASH = hashes.BLAKE2b(64)
    _ENCODING = serial.Encoding.PEM
    _BACKEND = default_backend()
    _PUBLIC_FORMAT = serial.PublicFormat.SubjectPublicKeyInfo
    _PRIVATE_FORMAT = serial.PrivateFormat.PKCS8
    _RATCHET_KDF = functools.partial(
        HKDF, _HASH, 64, salt=None, info=b"ratchet increment", backend=_BACKEND
    )

    __log: autologging.logging.Logger  # helps linter to detect autologging

    def encrypt_outgoing_message(self, message: bytes) -> str:

        new_base_key = self._RATCHET_KDF().derive(self._send_ratchet_key)
        self._send_ratchet_key = new_base_key[:32]
        fernet_key = base64.urlsafe_b64encode(new_base_key[32:])
        ciphertext = Fernet(fernet_key).encrypt(message)
        return ciphertext.decode("utf-8")

    @arg_to_bytes
    def decrypt_incoming_message(self, message: bstr) -> str:

        new_base_key = self._RATCHET_KDF().derive(self._recieve_ratchet_key)
        self._recieve_ratchet_key = new_base_key[:32]
        fernet_key = base64.urlsafe_b64encode(new_base_key[32:])
        plaintext = Fernet(fernet_key).decrypt(message)
        return plaintext.decode("utf-8")

    @property
    def public_chat_key(self) -> str:
        """
        return a PEM encoded serialized public key digest
        of a new ephemeral X448 key
        """
        self.__log.info("generating new public key")
        self._send_ratchet_key = b""
        self._recieve_ratchet_key = b""

        self._chat_key = X25519PrivateKey.generate()
        pub_key_bytes = self._chat_key.public_key().public_bytes(
            self._ENCODING, self._PUBLIC_FORMAT
        )
        return pub_key_bytes.decode("utf-8")

    @property
    def public_signing_key(self) -> str:
        """
        return a PEM encoded serialized public key digest
        of the ed448 signing key
        """
        key = self._signing_key.public_key()
        key_bytes = key.public_bytes(self._ENCODING, self._PUBLIC_FORMAT)
        return key_bytes.decode("utf-8")

    @arg_to_bytes
    def perform_key_exchange(self, public_key_bytes: bytes, chirality: bool):
        """
        ingest a PEM encoded public key and generate a symmetric key
        created by a Diffie-Helman key exchange result being passed into
        a key-derivation and used to create a fernet instance
        """
        public_key = serial.load_pem_public_key(public_key_bytes, self._BACKEND)
        if not isinstance(public_key, X25519PublicKey):
            raise ValueError("decoded public key was not a valid X448 public key")
        shared = self._chat_key.exchange(public_key)
        # TODO consider customizing symmetric encryption for larger key or authentication
        new_chat_key = self._RATCHET_KDF().derive(shared)
        if chirality:
            send_slice = slice(None, 32)
            recieve_slice = slice(32, None)
        else:
            send_slice = slice(32, None)
            recieve_slice = slice(None, 32)
        self._send_ratchet_key = new_chat_key[send_slice]
        self._recieve_ratchet_key = new_chat_key[recieve_slice]

    def make_signing_key(self):
        self._signing_key = Ed25519PrivateKey.generate()

    def sign_message(self, message: bytes) -> str:
        sig = self._signing_key.sign(message)
        return base64.urlsafe_b64encode(sig).decode("utf-8")

    def export_key(self, passphrase: bytes):
        key_bytes = self._signing_key.private_bytes(
            self._ENCODING,
            self._PRIVATE_FORMAT,
            serial.BestAvailableEncryption(passphrase),
        )
        return base64.urlsafe_b64encode(key_bytes).decode("utf-8")

    def import_key(self, key_bytes: bytes, passphrase: bytes):
        key_bytes = base64.urlsafe_b64decode(key_bytes)
        key = serial.load_pem_private_key(key_bytes, passphrase, self._BACKEND)
        if not isinstance(key, Ed25519PrivateKey):
            ValueError("key bytes did not decode to a valid Ed448 private key")
        self._signing_key
