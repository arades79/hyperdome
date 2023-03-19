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

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
import cryptography.hazmat.primitives.serialization as serial
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PublicKey

from hyperdome.server.database import Base, engine

from sqlalchemy import String, Column, Integer


class Counselor(Base):
    """
    container for counselors also responsible for holding keys and verifying messages
    """

    __tablename__ = "counselors"

    id = Column(
        Integer,
        primary_key=True,
    )
    name = Column(String(100), unique=True, nullable=False)
    key_bytes = Column(String(64), unique=True, nullable=False)

    # TODO: this should be in the cryptography common module and take pub_key as an argument
    # TODO: make into a pydantic type verification
    def verify(self, signature: bytes, message: bytes) -> bool:
        pub_key = serial.load_pem_public_key(self.key_bytes.encode(), default_backend())
        assert isinstance(pub_key, Ed448PublicKey)
        try:
            pub_key.verify(signature, message)
            return True
        except InvalidSignature:
            return False


class CounselorSignUp(Base):
    """
    model for storing valid counselor signup tokens
    """

    __tablename__ = "counselor_signup_tokens"

    id = Column(
        Integer,
        primary_key=True,
    )
    passphrase = Column(String(32), unique=True, nullable=False)


def create_models():
    Base.metadata.create_all(bind=engine)
