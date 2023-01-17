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

from datetime import timedelta
import hyperdome.common.encryption as enc
import pytest
from typing import Tuple, Callable
from hypothesis import given, assume, settings
import hypothesis.strategies as st
import cryptography

user_fixture = Callable[[], Tuple[enc.LockBox, enc.LockBox]]


@pytest.fixture(scope="module")
def pre_exchanged_user_factory():
    def factory():
        user_1_crypto = enc.LockBox()
        user_2_crypto = enc.LockBox()

        user_1_pub_key = user_1_crypto.public_chat_key
        user_2_pub_key = user_2_crypto.public_chat_key

        user_2_crypto.perform_key_exchange(user_1_pub_key, False)
        user_1_crypto.perform_key_exchange(user_2_pub_key, True)

        return user_1_crypto, user_2_crypto

    return factory


@given(message=st.text())
def test_encrypt_decrypt_message(
    pre_exchanged_user_factory: user_fixture, message: str
):
    user_1_crypto, user_2_crypto = pre_exchanged_user_factory()

    enc_message_1 = user_1_crypto.encrypt_outgoing_message(message.encode())
    enc_message_2 = user_2_crypto.encrypt_outgoing_message(message.encode())

    assert message != enc_message_1 != enc_message_2

    dec_message_1 = user_2_crypto.decrypt_incoming_message(enc_message_1)
    dec_message_2 = user_1_crypto.decrypt_incoming_message(enc_message_2)

    assert message.encode() == dec_message_1 == dec_message_2


@given(message=st.text())
def test_key_rotation(pre_exchanged_user_factory: user_fixture, message: str):
    user_1_crypto, user_2_crypto = pre_exchanged_user_factory()

    sent_message_1 = user_1_crypto.encrypt_outgoing_message(message.encode())
    sent_message_2 = user_1_crypto.encrypt_outgoing_message(message.encode())

    assert sent_message_1 != sent_message_2

    recieved_message_1 = user_2_crypto.decrypt_incoming_message(sent_message_1)
    recieved_message_2 = user_2_crypto.decrypt_incoming_message(sent_message_2)

    assert recieved_message_1 == recieved_message_2 == message.encode()


@given(message=st.text())
def test_no_double_decrypt(pre_exchanged_user_factory: user_fixture, message: str):
    user_1_crypto, user_2_crypto = pre_exchanged_user_factory()

    enc_message = user_1_crypto.encrypt_outgoing_message(message.encode())

    user_2_crypto.decrypt_incoming_message(enc_message)

    with pytest.raises(cryptography.fernet.InvalidToken) as e:
        user_2_crypto.decrypt_incoming_message(enc_message)


def test_signing_key_rotation():
    user = enc.LockBox()
    user.make_signing_key()
    pub_key_1 = user.public_signing_key
    user.make_signing_key()
    pub_key_2 = user.public_signing_key

    assert pub_key_1 != pub_key_2


@given(st.text(), st.text())
@settings(deadline=timedelta(milliseconds=500), max_examples=10)
def test_other_passphrases_cannot_import(passphrase_1: str, passphrase_2: str):
    assume(passphrase_1 != passphrase_2)
    assume(passphrase_1 and passphrase_2)
    user = enc.LockBox()
    user.make_signing_key()

    user_key = user.export_key(passphrase_1.encode())

    with pytest.raises(ValueError) as e:
        user.import_key(user_key, passphrase_2.encode())

    user.import_key(user_key, passphrase_1.encode())


@given(st.text())
@settings(deadline=timedelta(milliseconds=500), max_examples=10)
def test_import_export_same_pub_key(passphrase: str):
    assume(passphrase)

    passphrase_bytes = passphrase.encode()

    user = enc.LockBox()
    user.make_signing_key()
    initial_pub_key = user.public_signing_key

    exported_key = user.export_key(passphrase_bytes)

    user.make_signing_key()

    assert user.public_signing_key != initial_pub_key

    user.import_key(exported_key, passphrase_bytes)

    assert user.public_signing_key == initial_pub_key


@given(st.binary(min_size=32, max_size=32))
def test_x25519_from_ed25519(key_bytes: bytes):
    from hyperdome.common.key_conversion import (
        x25519_from_ed25519_private_key,
        x25519_from_ed25519_public_key,
        Encoding,
        PublicFormat,
        Ed25519PrivateKey,
    )

    pvk_ed = Ed25519PrivateKey.from_private_bytes(key_bytes)
    pbk_ed = pvk_ed.public_key()

    pvk_x = x25519_from_ed25519_private_key(pvk_ed)

    pbk_x1 = pvk_x.public_key()
    pbk_x2 = x25519_from_ed25519_public_key(pbk_ed)

    assert pbk_x1.public_bytes(Encoding.Raw, PublicFormat.Raw) == pbk_x2.public_bytes(
        Encoding.Raw, PublicFormat.Raw
    )
