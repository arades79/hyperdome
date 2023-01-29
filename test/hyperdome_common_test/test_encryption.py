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
import secrets
import hyperdome.common.encryption as enc
import pytest
from hypothesis import given, assume, settings
import hypothesis.strategies as st

from hyperdome.common.schemas import KeyExchangeBundle, PubKeyBytes


UserPair = tuple[enc.GuestKeyring, enc.CounselorKeyring]


@pytest.fixture(scope="module")
def pre_exchanged_users() -> UserPair:

    guest = enc.GuestKeyring()
    counselor = enc.CounselorKeyring()

    key_bundle = counselor.pre_key_bundle
    pub_signing_key = PubKeyBytes(
        counselor.public_signing_key.public_bytes(
            enc.Encoding.Raw, enc.PublicFormat.Raw
        )
    )
    ot_key = enc.PubKeyBytes(secrets.choice(key_bundle.one_time_keys))
    eph_key = enc.PubKeyBytes(
        guest.public_key.public_bytes(enc.Encoding.Raw, enc.PublicFormat.Raw)
    )

    counselor.exchange(
        enc.IntroductionMessage(ephemeral_key=eph_key, one_time_key=ot_key)
    )
    guest.exchange(
        KeyExchangeBundle(
            one_time_key=ot_key,
            pre_key_signature=key_bundle.pre_key_signature,
            signed_pre_key=key_bundle.signed_pre_key,
            pub_signing_key=pub_signing_key,
        )
    )

    return guest, counselor


@given(message=st.text())
def test_encrypt_decrypt_message(pre_exchanged_users: UserPair, message: str):
    guest, counselor = pre_exchanged_users

    guest_enc_message = guest.encrypt_message(message.encode())
    counselor_enc_message = counselor.encrypt_message(message.encode())

    assert (
        message.encode()
        != guest_enc_message.ciphertext
        != counselor_enc_message.ciphertext
    )

    dec_guest_message = counselor.decrypt_message(guest_enc_message)
    dec_counselor_message = guest.decrypt_message(counselor_enc_message)

    assert message.encode() == dec_counselor_message == dec_guest_message


@given(message=st.text())
def test_key_rotation(pre_exchanged_users: UserPair, message: str):
    guest, counselor = pre_exchanged_users

    sent_message_1 = guest.encrypt_message(message.encode())
    sent_message_2 = guest.encrypt_message(message.encode())

    assert sent_message_1.ciphertext != sent_message_2.ciphertext

    recieved_message_1 = counselor.decrypt_message(sent_message_1)
    recieved_message_2 = counselor.decrypt_message(sent_message_2)

    assert recieved_message_1 == recieved_message_2 == message.encode()


@given(message=st.text())
def test_no_double_decrypt(pre_exchanged_users: UserPair, message: str):
    guest, counselor = pre_exchanged_users

    enc_message = guest.encrypt_message(message.encode())

    counselor.decrypt_message(enc_message)

    with pytest.raises(ValueError) as _:
        counselor.decrypt_message(enc_message)


@given(message_1=st.text(), message_2=st.text(), message_3=st.text())
def test_out_of_order_recieve(
    pre_exchanged_users: UserPair, message_1: str, message_2: str, message_3: str
):
    guest, counselor = pre_exchanged_users

    enc_message_1 = guest.encrypt_message(message_1.encode())
    enc_message_2 = guest.encrypt_message(message_2.encode())
    enc_message_3 = guest.encrypt_message(message_3.encode())

    assert counselor.decrypt_message(enc_message_3) == message_3.encode()
    assert counselor.decrypt_message(enc_message_1) == message_1.encode()
    assert counselor.decrypt_message(enc_message_2) == message_2.encode()


# @given(st.text(), st.text())
# @settings(deadline=timedelta(milliseconds=500), max_examples=10)
# def test_other_passphrases_cannot_import(passphrase_1: str, passphrase_2: str):
#     assume(passphrase_1 != passphrase_2)
#     assume(passphrase_1 and passphrase_2)
#     user = enc.LockBox()
#     user.make_signing_key()

#     user_key = user.export_key(passphrase_1.encode())

#     with pytest.raises(ValueError) as _:
#         user.import_key(user_key, passphrase_2.encode())

#     user.import_key(user_key, passphrase_1.encode())


# @given(st.text())
# @settings(deadline=timedelta(milliseconds=500), max_examples=10)
# def test_import_export_same_pub_key(passphrase: str):
#     assume(passphrase)

#     passphrase_bytes = passphrase.encode()

#     user = enc.LockBox()
#     user.make_signing_key()
#     initial_pub_key = user.public_signing_key

#     exported_key = user.export_key(passphrase_bytes)

#     user.make_signing_key()

#     assert user.public_signing_key != initial_pub_key

#     user.import_key(exported_key, passphrase_bytes)

#     assert user.public_signing_key == initial_pub_key


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
