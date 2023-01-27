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

import secrets

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
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

from hyperdome.common.key_conversion import (
    x25519_from_ed25519_private_key,
    x25519_from_ed25519_public_key,
)

from hyperdome.common.schemas import (
    EncryptedMessage,
    KeyExchangeBundle,
    IntroductionMessage,
    NewPreKeyBundle,
    PubKeyBytes,
)


class KeyRatchet:
    """
    HKDF key ratchet using blake2b digests generating one-time use 256-bit key material.

    This construct should only be initialized with bytes suitable for key material.

    This construct only does key management, not encryption/decryption.
    """

    key_derivation_function = HKDF(
        hashes.BLAKE2b(64),
        64,
        b"g9V1g/blZmlPV1wXTxwTWRokO5HCvLOY",
        b"key ratchet increment",
        default_backend(),
    )

    def __init__(self, initial_key_material: bytes):
        if len(initial_key_material) != 32:
            raise ValueError("initial key material must be 32 bytes")
        self._kdf_key = initial_key_material
        self._increment()
        self._counter: int = 0

    def _increment(self):
        new_key_bytes = self.key_derivation_function.derive(self._kdf_key)
        self._kdf_key = new_key_bytes[32:]
        self._enc_key = new_key_bytes[:32]
        self._counter += 1

    @property
    def key(self):
        ret_key = self._enc_key
        self._increment()
        return ret_key

    @property
    def counter(self):
        return self._counter


class MessageEncryptor:
    def __init__(self, initial_key_material: bytes):
        self._ratchet = KeyRatchet(initial_key_material)

    def encrypt(
        self, plaintext: bytes, associated_data: bytes | None = None
    ) -> EncryptedMessage:
        nonce = secrets.token_bytes(12)
        sequence = self._ratchet.counter
        key = ChaCha20Poly1305(self._ratchet.key)
        ciphertext = key.encrypt(nonce, plaintext, associated_data)
        return EncryptedMessage(
            **{
                "nonce": nonce,
                "sequence": sequence,
                "ciphertext": ciphertext,
                "associated_data": associated_data,
            }
        )


class MessageDecryptor:
    def __init__(self, initial_key_material: bytes):
        self._ratchet = KeyRatchet(initial_key_material)
        self._run_ahead_buffer: dict[int, ChaCha20Poly1305] = dict()

    def _run_ahead(self, iterations: int):
        for _ in range(iterations):
            self._run_ahead_buffer[self._ratchet.counter] = ChaCha20Poly1305(
                self._ratchet.key
            )

    def decrypt(self, message: EncryptedMessage) -> bytes:
        counter = self._ratchet.counter
        if message.sequence > counter:
            self._run_ahead(message.sequence - counter)

        if message.sequence == counter:
            key = ChaCha20Poly1305(self._ratchet.key)
        elif message.sequence in self._run_ahead_buffer.keys():
            key = self._run_ahead_buffer.pop(message.sequence)
        else:
            raise ValueError("impossible to decrypt message with given sequence")

        plaintext = key.decrypt(
            message.nonce, message.ciphertext, message.associated_data
        )
        return plaintext


class HA3DH:

    key_derivation_function = HKDF(
        hashes.BLAKE2b(64),
        64,
        b"g9V1g/blZmlPV1wXTxwTWRokO5HCvLOY",
        b"diffie hellman key exchange",
        default_backend(),
    )

    @staticmethod
    def exchange(
        cid_key: Ed25519PublicKey | Ed25519PrivateKey,
        csp_key: X25519PrivateKey | X25519PublicKey,
        eph_key: X25519PublicKey | X25519PrivateKey,
        ot_key: X25519PrivateKey | X25519PublicKey,
        csp_sig: bytes | None = None,
    ) -> tuple[MessageEncryptor, MessageDecryptor]:
        if (
            isinstance(cid_key, Ed25519PrivateKey)
            and csp_sig is None
            and isinstance(csp_key, X25519PrivateKey)
            and isinstance(eph_key, X25519PublicKey)
            and isinstance(ot_key, X25519PrivateKey)
        ):
            dh1 = x25519_from_ed25519_private_key(cid_key).exchange(eph_key)
            dh2 = csp_key.exchange(eph_key)
            dh3 = ot_key.exchange(eph_key)
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
                csp_sig, csp_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
            )
            dh1 = eph_key.exchange(x25519_from_ed25519_public_key(cid_key))
            dh2 = eph_key.exchange(csp_key)
            dh3 = eph_key.exchange(ot_key)
            send_slice = slice(32, None)
            recv_slice = slice(None, 32)
        else:
            raise TypeError("public/private key mismatch")
        shared_secret = HA3DH.key_derivation_function.derive(dh1 + dh2 + dh3)
        send_ratchet = MessageEncryptor(shared_secret[send_slice])
        recv_ratchet = MessageDecryptor(shared_secret[recv_slice])
        return (send_ratchet, recv_ratchet)


class GuestKeyring:
    def __init__(self):
        self._private_key = X25519PrivateKey.generate()
        self.public_key = self._private_key.public_key()

    def exchange(self, key_bundle: KeyExchangeBundle):
        if self._private_key is None:
            raise ValueError(
                "Guest keyring was already used to exchange!\n"
                "A new GuestKeyring must be generated for each exchange"
            )
        cid_key = Ed25519PublicKey.from_public_bytes(key_bundle.pub_signing_key)
        csp_key = X25519PublicKey.from_public_bytes(key_bundle.signed_pre_key)
        ot_key = X25519PublicKey.from_public_bytes(key_bundle.one_time_key)
        (self._encryptor, self._decryptor) = HA3DH.exchange(
            cid_key, csp_key, self._private_key, ot_key, key_bundle.pre_key_signature
        )
        self._private_key = None

    def encrypt_message(
        self, message: bytes, associated_data: bytes | None = None
    ) -> EncryptedMessage:
        return self._encryptor.encrypt(message, associated_data)

    def decrypt_message(self, message: EncryptedMessage) -> bytes:
        return self._decryptor.decrypt(message)


class CounselorKeyring:
    def __init__(self) -> None:
        self._private_signing_key = Ed25519PrivateKey.generate()
        self.public_signing_key = self._private_signing_key.public_key()

        self._pre_key = X25519PrivateKey.generate()
        self._one_time_key_pairs: dict[PubKeyBytes, X25519PrivateKey] = dict()
        self._generate_one_time_keys()

    def _generate_one_time_keys(self):
        for _ in range(100):
            key = X25519PrivateKey.generate()
            key_bytes = PubKeyBytes(
                key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            )
            self._one_time_key_pairs[key_bytes] = key

    def sign(self, data: bytes):
        return self._private_signing_key.sign(data)

    @property
    def pre_key_signature(self):
        key_bytes = self._pre_key.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        return self.sign(key_bytes)

    @property
    def one_time_keys_signature(self):
        key_bytes = b""
        for key in self._one_time_key_pairs.keys():
            key_bytes += key
        return self.sign(key_bytes)

    @property
    def pre_key_bundle(self):
        return NewPreKeyBundle(
            **{
                "signed_pre_key": self._pre_key.public_key().public_bytes(
                    Encoding.Raw, PublicFormat.Raw
                ),
                "pre_key_signature": self.pre_key_signature,
                "one_time_keys": self._one_time_key_pairs.keys(),
                "one_time_keys_signature": self.one_time_keys_signature,
            }
        )

    def exchange(self, key_bundle: IntroductionMessage):
        eph_key = X25519PublicKey.from_public_bytes(key_bundle.ephemeral_key)
        ot_key = self._one_time_key_pairs.pop(key_bundle.one_time_key)

        (self._encryptor, self._decryptor) = HA3DH.exchange(
            self._private_signing_key, self._pre_key, eph_key, ot_key
        )

    def encrypt_message(
        self, message: bytes, associated_data: bytes | None = None
    ) -> EncryptedMessage:
        return self._encryptor.encrypt(message, associated_data)

    def decrypt_message(self, message: EncryptedMessage) -> bytes:
        return self._decryptor.decrypt(message)
