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

import hyperdome.common.encryption as enc
import pytest
from typing import Tuple

user_fixture = Tuple[enc.LockBox, enc.LockBox]


@pytest.fixture
def pre_exchanged_users():
    user_1_crypto = enc.LockBox()
    user_2_crypto = enc.LockBox()

    user_1_pub_key = user_1_crypto.public_chat_key
    user_2_pub_key = user_2_crypto.public_chat_key

    user_2_crypto.perform_key_exchange(user_1_pub_key, False)
    user_1_crypto.perform_key_exchange(user_2_pub_key, True)

    return user_1_crypto, user_2_crypto


def test_encrypt_decrypt_message(pre_exchanged_users: user_fixture):
    user_1_crypto, user_2_crypto = pre_exchanged_users

    message = "eat pant"

    enc_message_1 = user_1_crypto.encrypt_outgoing_message(message)
    enc_message_2 = user_2_crypto.encrypt_outgoing_message(message)

    assert message != enc_message_1 != enc_message_2

    dec_message_1 = user_2_crypto.decrypt_incoming_message(enc_message_1)
    dec_message_2 = user_1_crypto.decrypt_incoming_message(enc_message_2)

    assert message == dec_message_1 == dec_message_2


def test_key_rotation(pre_exchanged_users: user_fixture):
    user_1_crypto, user_2_crypto = pre_exchanged_users

    message = "eat pant"

    sent_message_1 = user_1_crypto.encrypt_outgoing_message(message)
    sent_message_2 = user_1_crypto.encrypt_outgoing_message(message)

    assert sent_message_1 != sent_message_2

    recieved_message_1 = user_2_crypto.decrypt_incoming_message(sent_message_1)
    recieved_message_2 = user_2_crypto.decrypt_incoming_message(sent_message_2)

    assert recieved_message_1 == recieved_message_2 == message


def test_no_double_decrypt(pre_exchanged_users: user_fixture):

    message = "eat pant"

    enc_message = pre_exchanged_users[0].encrypt_outgoing_message(message)

    pre_exchanged_users[1].decrypt_incoming_message(enc_message)

    # TODO use more specific exception and use info
    with pytest.raises(Exception) as e:
        pre_exchanged_users[1].decrypt_incoming_message(enc_message)


def test_rotation_cannot_decrypt(pre_exchanged_users: user_fixture):

    message = "eat pant"

    enc_message = pre_exchanged_users[0].encrypt_outgoing_message(message)

    prev_chat_key = pre_exchanged_users[1]._chat_key

    _ = pre_exchanged_users[1].public_chat_key

    new_chat_key = pre_exchanged_users[1]._chat_key

    assert prev_chat_key != new_chat_key

    # TODO use more specific exception and use info
    with pytest.raises(Exception) as e:
        pre_exchanged_users[1].decrypt_incoming_message(enc_message)
