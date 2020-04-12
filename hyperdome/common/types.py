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

import typing
import functools
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PublicKey

bstr = typing.Union[str, bytes]

key_type = typing.Union[bstr, Ed448PublicKey]


def arg_to_bytes(fn):
    @functools.wraps(fn)
    def converted(*args, **kwargs):
        args = [(arg.encode() if isinstance(arg, str) else arg) for arg in args]
        kwargs = {
            key: (value.encode() if isinstance(value, str) else value)
            for key, value in kwargs.items()
        }
        return fn(*args, **kwargs)

    return converted
