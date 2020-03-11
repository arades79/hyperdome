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
import base64
import hashlib
import inspect
import os
import platform
import random
import socket
import sys
import threading
import time

from .settings import Settings


# TODO there's a lot of platform-specific pathing here, we can probably
# just use pathlib to get rid of a lot of code
class Common(object):
    """
    The Common object is shared amongst all parts of OnionShare.
    """

    def __init__(self, debug=False):
        self.debug = debug

        # The platform OnionShare is running on
        self.platform = platform.system()
        if self.platform.endswith('BSD'):
            self.platform = 'BSD'

        # The current version of OnionShare
        with open(self.get_resource_path('version.txt')) as f:
            self.version = f.read().strip()

    def load_settings(self, config=''):
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
                final_msg = '{}: {}'.format(final_msg, msg)
            print(final_msg)

    def get_resource_path(self, filename):
        """
        Returns the absolute path of a resource, regardless of whether
        OnionShare is installed systemwide, and whether regardless of platform
        """
        # On Windows, and in Windows dev mode, switch slashes in incoming
        # filename to backslackes
        if self.platform == 'Windows':
            filename = filename.replace('/', '\\')

        if getattr(sys, 'onionshare_dev_mode', False):
            # Look for resources directory relative to python file
            prefix = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(
                    inspect.getfile(inspect.currentframe())))),
                'share')
            if not os.path.exists(prefix):
                # While running tests during stdeb bdist_deb, look 3
                # directories up for the share folder
                prefix = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(
                        os.path.dirname(prefix)))),
                    'share')

        elif self.platform == 'BSD' or self.platform == 'Linux':
            # Assume OnionShare is installed systemwide in Linux, since we're
            # not running in dev mode
            prefix = os.path.join(sys.prefix, 'share/onionshare')

        elif getattr(sys, 'frozen', False):
            # Check if app is "frozen"
            # https://pythonhosted.org/PyInstaller/#run-time-information
            if self.platform == 'Darwin':
                prefix = os.path.join(sys._MEIPASS, 'share')
            elif self.platform == 'Windows':
                prefix = os.path.join(os.path.dirname(sys.executable), 'share')
            else:
                raise SystemError
        else:
            raise SystemError

        return os.path.join(prefix, filename)

    def get_tor_paths(self):
        if self.platform == 'Linux':
            tor_path = '/usr/bin/tor'
            tor_geo_ip_file_path = '/usr/share/tor/geoip'
            tor_geo_ipv6_file_path = '/usr/share/tor/geoip6'
            obfs4proxy_file_path = '/usr/bin/obfs4proxy'
        elif self.platform == 'Windows':
            base_path = os.path.join(
                os.path.dirname(os.path.dirname(self.get_resource_path(''))),
                'tor')
            tor_path = os.path.join(os.path.join(base_path, 'Tor'), 'tor.exe')
            obfs4proxy_file_path = os.path.join(
                os.path.join(base_path, 'Tor'), 'obfs4proxy.exe')
            tor_geo_ip_file_path = os.path.join(os.path.join(
                os.path.join(base_path, 'Data'), 'Tor'), 'geoip')
            tor_geo_ipv6_file_path = os.path.join(os.path.join(
                os.path.join(base_path, 'Data'), 'Tor'), 'geoip6')
        elif self.platform == 'Darwin':
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(
                self.get_resource_path(''))))
            tor_path = os.path.join(base_path, 'Resources', 'Tor', 'tor')
            tor_geo_ip_file_path = os.path.join(
                base_path, 'Resources', 'Tor', 'geoip')
            tor_geo_ipv6_file_path = os.path.join(
                base_path, 'Resources', 'Tor', 'geoip6')
            obfs4proxy_file_path = os.path.join(
                base_path, 'Resources', 'Tor', 'obfs4proxy')
        elif self.platform == 'BSD':
            tor_path = '/usr/local/bin/tor'
            tor_geo_ip_file_path = '/usr/local/share/tor/geoip'
            tor_geo_ipv6_file_path = '/usr/local/share/tor/geoip6'
            obfs4proxy_file_path = '/usr/local/bin/obfs4proxy'

        return (tor_path, tor_geo_ip_file_path, tor_geo_ipv6_file_path,
                obfs4proxy_file_path)

    def build_data_dir(self):
        """
        Returns the path of the OnionShare data directory.
        """
        if self.platform == 'Windows':
            if 'APPDATA' in os.environ:
                appdata = os.environ['APPDATA']
                onionshare_data_dir = '{}\\OnionShare'.format(appdata)
            else:
                # If for some reason we don't have the 'APPDATA' environment
                # variable (like running tests in Linux while pretending
                # to be in Windows)
                onionshare_data_dir = os.path.expanduser(
                    '~/.config/onionshare')
        elif self.platform == 'Darwin':
            onionshare_data_dir = os.path.expanduser(
                '~/Library/Application Support/OnionShare')
        else:
            onionshare_data_dir = os.path.expanduser('~/.config/onionshare')

        os.makedirs(onionshare_data_dir, 0o700, True)
        return onionshare_data_dir


    @staticmethod
    def random_string(num_bytes, output_len=None):
        """
        Returns a random string with a specified number of bytes.
        """
        b = os.urandom(num_bytes)
        h = hashlib.sha256(b).digest()[:16]
        s = base64.b32encode(h).lower().replace(b'=', b'').decode('utf-8')
        return s[:output_len] if output_len else s


    @staticmethod
    def get_available_port(min_port, max_port):
        """
        Find a random available port within the given range.
        """
        with socket.socket() as tmpsock:
            while True:
                try:
                    tmpsock.bind(("127.0.0.1", random.randint(min_port,
                                                              max_port)))
                    break
                except OSError:
                    pass
            _, port = tmpsock.getsockname()
        return port


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
        self.common.log('Shutdown Timer',
                        'Server will shut down after {} seconds'.format(
                            self.time))
        time.sleep(self.time)
        return 1
