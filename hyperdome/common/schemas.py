# -*- coding: utf-8 -*-
"""
Hyperdome

Copyright (C) 2023 Skyelar Craver <scravers@protonmail.com>
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

# GET /counselor -> {pub_key, signed_pre_key, pre_key_signature, one_time_key} - randomly assigned available counselor, requires auth cookie, random otk picked and deleted
# POST /counselor/{pub_key} <- {signed_pre_key, pre_key_signature, set_of_one_time_keys} - also set auth cookie
# POST /counselor <- {pub_key, signed_registration_code, signature}
# POST /guest <- {identity_key} - also set auth cookie
# WS /chat - requires auth cookie
# 	- counselor opens immediately and waits for connection
# 	- counselor is sent GIK after being assigned
# 	- guest connects after getting counselor key pack, verifies signature or closes connection
# 	- guest performs DH(GIK,CIK), DH(GEK,CIK), DH(GEK,CSPK), DH(GEK,COTK)
# 		 - initialize ratchets with KDF(DH1 | DH2 | DH3 | DH4), lower 32 bytes for recieve, upper 32 bytes for send
# 		 - create hello_cipher_text by encrypting message "hello" with hash(GIK | CIK) as AD
# 	- guest sends {eph_key, counselor_one_time_key, hello_cipher_text} introduction
# 	- counselor recieves introduction, verifies signature or closes connection
# 	- counselor performs DH(GIK,CIK), DH(GEK,CIK), DH(GEK,CSPK), DH(GEK,COTK)
# 		- initialize ratchets with KDF(DH1 | DH2 | DH3 | DH4), upper 32 bytes for recieve, lower 32 bytes for send
# 	- users exchange messages {send_ratchet_sequence_num, encrypted_message, nonce}
# 	- ratchets consume 32 byte key in KDF, KDF supplies 64 bytes, truncate KDF output to 32 bytes for next ratchet
# 	- using ChaChaPoly1305 as AEAD cipher, random 12 byte nonce generated per message
# 	- sequence number included as authenticated data

from enum import StrEnum, auto
from pydantic import BaseModel, Field, Required, ConstrainedBytes


class PubKeyBytes(ConstrainedBytes):
    min_length = 32
    max_length = 32


class SignatureBytes(ConstrainedBytes):
    min_length = 64
    max_length = 64


class NonceBytes(ConstrainedBytes):
    min_length = 12
    max_length = 12


class NewPreKeyBundle(BaseModel):
    signed_pre_key: PubKeyBytes = Required
    pre_key_signature: SignatureBytes = Required
    one_time_keys: list[PubKeyBytes] = Required
    one_time_keys_signature: SignatureBytes = Required


class KeyExchangeBundle(BaseModel):
    pub_signing_key: PubKeyBytes = Required
    signed_pre_key: PubKeyBytes = Required
    pre_key_signature: SignatureBytes = Required
    one_time_key: PubKeyBytes = Required


class Counselor(BaseModel):
    pub_signing_key: PubKeyBytes = Required
    signed_pre_key: PubKeyBytes = Field(b"\x00" * 32)
    pre_key_signature: SignatureBytes = Field(b"\x00" * 64)
    one_time_keys: list[PubKeyBytes] = Field(
        default_factory=list,
    )


class CounselorSignup(BaseModel):
    pub_signing_key: PubKeyBytes = Required
    signed_registration_code: PubKeyBytes = Required
    registration_code_signature: SignatureBytes = Required


class ChatContentType(StrEnum):
    INTRODUCTION = auto()
    ENCRYPTED_MESSAGE = auto()
    STATUS = auto()


class IntroductionMessage(BaseModel):
    ephemeral_key: PubKeyBytes = Required
    one_time_key: PubKeyBytes = Required


class EncryptionScheme(BaseModel):
    version: str = "v1"
    cipher: str = "ChaCha20Poly1305"
    exchange: str = "Ed25519+X25519+X25519"
    hash: str = "BLAKE2b"


DEFAULT_ENCRYPTION_SCHEME = EncryptionScheme()


class EncryptedMessage(BaseModel):
    sequence: int = Required
    nonce: NonceBytes
    ciphertext: bytes = Required
    encryption: EncryptionScheme = DEFAULT_ENCRYPTION_SCHEME


class StatusType(StrEnum):
    DISCONNECT = auto()


class StatusMessage(BaseModel):
    status: StatusType


class ChatContent(BaseModel):
    _type: ChatContentType = Required
    content: IntroductionMessage | EncryptedMessage | StatusMessage = Required
