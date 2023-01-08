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

import autologging
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
import cryptography.hazmat.primitives.serialization as serial

from ..common.types import arg_to_bytes, bstr
from .app import db


@autologging.traced
@autologging.logged
class Counselor(db.Model):
    """
    container for counselors also responsible for holding keys and verifying messages
    """

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    name = db.Column(db.String(100), unique=True, nullable=False)
    key_bytes = db.Column(db.String(64), unique=True, nullable=False)

    # TODO: this should be in the cryptography common module and take pub_key as an argument
    @arg_to_bytes
    def verify(self, signature: bstr, message: bstr) -> bool:
        pub_key = serial.load_pem_public_key(self.key_bytes.encode(), default_backend())
        try:
            pub_key.verify(signature, message)
            return True
        except InvalidSignature:
            return False


@autologging.traced
@autologging.logged
class CounselorSignUp(db.Model):
    """
    model for storing valid counselor signup tokens
    """

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    passphrase = db.Column(db.String(32), unique=True, nullable=False)


db.create_all()
