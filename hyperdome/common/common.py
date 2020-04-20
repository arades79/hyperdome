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

import socket
import sys
import threading
import time
import secrets
from pathlib import Path
from .settings import Settings
import platform
from .utils import bootstrap


platform_str = "BSD" if platform.system().endswith("BSD") else platform.system()

resource_path = Path(getattr(sys, "_MEIPASS", "."), "share").resolve(strict=True)

version = Path(resource_path, "version.txt").read_text().strip()


@bootstrap
def data_path():
    """
    Returns the path of the hyperdome data directory.
    """
    if (appdata := Path("~", "AppData", "Roaming")).exists():
        hyperdome_data_dir = appdata / "hyperdome"
    elif platform_str == "Darwin":
        hyperdome_data_dir = Path("~/Library/Application Support/hyperdome")
    else:
        hyperdome_data_dir = Path("~/.config/hyperdome")

    hyperdome_data_dir.mkdir(0o700, True)
    return hyperdome_data_dir.resolve()


@bootstrap
def tor_paths():
    if platform_str == "Linux":
        tor_path = Path("/usr/bin/tor")
        tor_geo_ip_file_path = Path("/usr/share/tor/geoip")
        tor_geo_ipv6_file_path = Path("/usr/share/tor/geoip6")
        obfs4proxy_file_path = Path("/usr/bin/obfs4proxy")
    elif platform_str == "Windows":
        base_path = resource_path.parents[1] / "tor"
        tor_path = base_path / "Tor" / "tor.exe"
        obfs4proxy_file_path = base_path / "Tor" / "obfs4proxy.exe"
        tor_geo_ip_file_path = base_path / "Data" / "Tor" / "geoip"
        tor_geo_ipv6_file_path = base_path / "Data" / "Tor" / "geoip6"
    elif platform_str == "Darwin":
        base_path = resource_path.parents[1]
        tor_path = base_path / "Resources" / "Tor" / "tor"
        tor_geo_ip_file_path = base_path / "Resources" / "Tor" / "geoip"
        tor_geo_ipv6_file_path = base_path / "Resources" / "Tor" / "geoip6"
        obfs4proxy_file_path = base_path / "Resources" / "Tor" / "obfs4proxy"
    elif platform_str == "BSD":
        tor_path = Path("/usr/local/bin/tor")
        tor_geo_ip_file_path = Path("/usr/local/share/tor/geoip")
        tor_geo_ipv6_file_path = Path("/usr/local/share/tor/geoip6")
        obfs4proxy_file_path = Path("/usr/local/bin/obfs4proxy")
    else:
        raise OSError("Host platform not supported")

    return (
        tor_path,
        tor_geo_ip_file_path,
        tor_geo_ipv6_file_path,
        obfs4proxy_file_path,
    )


def get_available_port(min_port, max_port):
    """
    Find a random available port within the given range.
    """
    with socket.socket() as tmpsock:
        while True:
            try:
                tmpsock.bind(("127.0.0.1", secrets.choice(range(min_port, max_port))))
                break
            except OSError:
                pass
        _, port = tmpsock.getsockname()
    return port


# TODO there's a lot of platform_str-specific pathing here, we can probably
# just use pathlib to get rid of a lot of code
class Common(object):
    """
    The Common object is shared amongst all parts of hyperdome.
    """

    def __init__(self, debug=False):
        self.debug = debug

    def load_settings(self, config=""):
        """
        Loading settings, optionally from a custom config json file.
        """
        self.settings = Settings(self, config)
        self.settings.load()

    def log(self, module, func, msg=None):
        """
        If debug mode is on, log error messages to stdout
        """
        if self.debug:
            timestamp = time.strftime("%b %d %Y %X")

            final_msg = "[{}] {}.{}".format(timestamp, module, func)
            if msg:
                final_msg = "{}: {}".format(final_msg, msg)
            print(final_msg)


class ShutdownTimer(threading.Thread):
    """
    Background thread sleeps t hours and returns.
    """

    def __init__(self, common, time):
        threading.Thread.__init__(self)

        self.common = common

        self.setDaemon(True)
        self.time = time

    def run(self):
        self.common.log(
            "Shutdown Timer", "Server will shut down after {} seconds".format(self.time)
        )
        time.sleep(self.time)
        return 1
