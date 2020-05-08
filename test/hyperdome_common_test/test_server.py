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

import hyperdome.common.server as svr
import pytest
from hypothesis import given, assume
from hypothesis.strategies import text

# CIA onion v3 address - known working as of 05/04/20
KNOWN_GOOD_ONIONV3_KEY = "ciadotgov4sjwlzihbbgxnqg3xiyrg7so2r2o3lt5wz5ypk4sxyjstad"


def test_good_urls():
    full_url = f"http://{KNOWN_GOOD_ONIONV3_KEY}.onion/"
    key_only = KNOWN_GOOD_ONIONV3_KEY

    full_url_server = svr.Server(url=full_url)
    key_only_server = svr.Server(url=key_only)

    assert full_url_server.url == key_only_server.url


@given(text(max_size=55))
def test_random_text_fails(url: str):
    assume(url.strip().strip("/"))
    with pytest.raises(svr.Server.InvalidOnionAddress) as e:
        _ = svr.Server(url=url)
