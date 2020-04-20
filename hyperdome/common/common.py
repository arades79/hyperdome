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

import json
import locale
from pathlib import Path
import platform
import secrets
import socket
import sys
import threading
import time
import typing

from .utils import bootstrap


platform_str = "BSD" if platform.system().endswith("BSD") else platform.system()

resource_path = Path(getattr(sys, "_MEIPASS", "."), "share").resolve(strict=True)

version = Path(resource_path, "version.txt").read_text().strip()


@bootstrap
def data_path() -> Path:
    """
    Returns the path of the hyperdome data directory.
    """
    home = Path.home()
    if (appdata := (home / "AppData" / "Roaming")).exists():
        hyperdome_data_dir = appdata / "hyperdome"
    elif platform_str == "Darwin":
        hyperdome_data_dir = home / "Library" / "Application Support" / "hyperdome"
    else:
        hyperdome_data_dir = home / ".config" / "hyperdome"
    if not hyperdome_data_dir.is_dir():
        hyperdome_data_dir.mkdir(0o700)
    return hyperdome_data_dir.resolve()


@bootstrap
def tor_paths() -> typing.Tuple[Path, Path, Path, Path]:
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


def get_available_port(min_port: int, max_port: int) -> int:
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


class Settings(object):
    """
    This class stores all of the settings for hyperdome, specifically for how
    to connect to Tor. If it can't find the settings file, it uses the default,
    which is to attempt to connect automatically using default Tor Browser
    settings.
    """

    def __init__(self, common, config: str = ""):
        self.common = common

        self.common.log("Settings", "__init__")

        # If a readable config file was provided, use that
        if config:
            if (config_path := Path(config)).exists():
                self.filename = config_path
            else:
                self.common.log(
                    "Settings",
                    "__init__",
                    "Supplied config does not exist or is "
                    "unreadable. Falling back to default location",
                )
        else:
            self.filename: Path = data_path / "hyperdome.json"

        # Dictionary of available languages in this version of hyperdome,
        # mapped to the language name, in that language
        self.available_locales = {
            # 'bn': 'বাংলা',       # Bengali
            # 'ca': 'Català',     # Catalan
            # 'da': 'Dansk',      # Danish
            "en": "English",  # English
            # 'fr': 'Français',   # French
            # 'el': 'Ελληνικά',   # Greek
            # 'it': 'Italiano',   # Italian
            # 'ja': '日本語',      # Japanese
            # 'fa': 'فارسی',      # Persian
            # 'pt_BR': 'Português (Brasil)',  # Portuguese Brazil
            # 'ru': 'Русский',    # Russian
            # 'es': 'Español',    # Spanish
            # 'sv': 'Svenska'     # Swedish
        }

        # These are the default settings. They will get overwritten when
        # loading from disk
        self.default_settings = {
            "version": version,
            "connection_type": "automatic",
            "control_port_address": "127.0.0.1",
            "control_port_port": 9051,
            "socks_address": "127.0.0.1",
            "socks_port": 9050,
            "socket_file_path": "/var/run/tor/control",
            "auth_type": "no_auth",
            "auth_password": "",
            "shutdown_timeout": False,
            "autoupdate_timestamp": None,
            "no_bridges": True,
            "tor_bridges_use_obfs4": False,
            "tor_bridges_use_meek_lite_azure": False,
            "tor_bridges_use_custom_bridges": "",
            "save_private_key": True,  # should be renamed for clarity,
            # perhaps "use ephemeral"
            "private_key": "",
            "hidservauth_string": "",
            "locale": None,  # this gets defined in fill_in_defaults()
        }
        self._settings: dict[str] = {}
        self.fill_in_defaults()

    def fill_in_defaults(self):
        """
        If there are any missing settings from self._settings, replace them
        with their default values.
        """
        for key in self.default_settings:
            if key not in self._settings:
                self._settings[key] = self.default_settings[key]

        # Choose the default locale based on the OS preference, and fall-back
        # to English
        if self._settings["locale"] is None:
            language_code, _ = locale.getdefaultlocale()

            # Default to English
            if not language_code:
                language_code = "en_US"

            if language_code == "pt_PT" and language_code == "pt_BR":
                # Steven: What? How would this be possible unless
                # it's overriding the == operator in a stupid way?
                # Portuguese locales include country code
                default_locale = language_code
            else:
                # All other locales cut off the country code
                default_locale = language_code[:2]

            if default_locale not in self.available_locales:
                default_locale = "en"
            self._settings["locale"] = default_locale

    def load(self):
        """
        Load the settings from file.
        """
        self.common.log("Settings", "load")

        # If the settings file exists, load it
        if self.filename.exists():
            self.common.log(
                "Settings", "load", "Trying to load {}".format(self.filename)
            )
            self._settings = json.loads(self.filename.read_text())
            self.fill_in_defaults()

    def save(self):
        """
        Save settings to file.
        """
        self.common.log("Settings", "save")
        self.filename.write_text(json.dumps(self._settings))
        self.common.log(
            "Settings", "save", "Settings saved in {}".format(self.filename)
        )

    def get(self, key: str):
        return self._settings[key]

    def set(self, key: str, val):
        # If typecasting int values fails, fallback to default values
        if key in ("control_port_port", "socks_port"):
            try:
                val = int(val)
            except ValueError:
                val = self.default_settings[key]

        self._settings[key] = val

    def clear(self):
        """
        Clear all settings and re-initialize to defaults
        """
        self._settings = self.default_settings
        self.fill_in_defaults()
        self.save()


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
