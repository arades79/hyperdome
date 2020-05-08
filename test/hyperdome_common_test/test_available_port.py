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

from hyperdome.common.common import get_available_port
from hypothesis import given, assume
import hypothesis.strategies as st
import pytest
import socket

MAX_PORT = 65535
MIN_PORT = 0

MAX_USED_PORT = 62125
MIN_USED_PORT = 62105

MAX_UNUSED_PORT = 63125
MIN_UNUSED_PORT = 63105


@pytest.fixture(scope="session")
def bound_ports():
    sockets = []
    for i in range(MIN_USED_PORT, MAX_USED_PORT + 1):
        try:
            s = socket.socket()
            s.bind(("127.0.0.1", i))
            sockets.append(s)
        except OSError:
            pass

    yield None

    [s.close() for s in sockets]


@given(st.integers(min_value=MAX_PORT), st.integers(min_value=MAX_PORT))
def test_max_port_error(port_min, port_max):

    with pytest.raises(ValueError) as e:
        get_available_port(port_min, port_max)


@given(st.integers(max_value=MIN_PORT), st.integers(max_value=MIN_PORT))
def test_min_port_error(port_min, port_max):

    with pytest.raises(ValueError) as e:
        get_available_port(port_min, port_max)


@given(st.text(), st.floats())
def test_not_integer_error(min_port, max_port):

    with pytest.raises(TypeError) as e:
        get_available_port(min_port, 65000)

    with pytest.raises(TypeError) as e:
        get_available_port(1000, max_port)


@given(min_port=st.just(MIN_USED_PORT), max_port=st.just(MAX_USED_PORT))
def test_bound_ports_error(bound_ports, min_port, max_port):

    with pytest.raises(OSError) as e:
        get_available_port(min_port, max_port)


@given(
    min_port=st.integers(MIN_UNUSED_PORT, MAX_UNUSED_PORT),
    max_port=st.integers(MIN_UNUSED_PORT, MAX_UNUSED_PORT),
)
def test_unused_port(min_port, max_port):
    assume(min_port < max_port - 1)
    port = get_available_port(min_port, max_port)
    assert min_port <= port <= max_port
