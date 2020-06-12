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

from distutils.version import LooseVersion as Version
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

import autologging
from stem import ProtocolError, SocketClosed, SocketError
import stem
from stem.connection import AuthenticationFailure, MissingPassword, UnreadableCookieFile
from stem.control import Controller

from . import strings
from .common import (
    data_path,
    get_available_port,
    platform_str,
    resource_path,
    tor_paths,
)


class TorErrorAutomatic(Exception):
    """
    hyperdome is failing to connect and authenticate to the Tor controller,
    using automatic settings that should work with Tor Browser.
    """

    pass


class TorErrorInvalidSetting(Exception):
    """
    This exception is raised if the settings just don't make sense.
    """

    pass


class TorErrorSocketPort(Exception):
    """
    hyperdome can't connect to the Tor controller using the supplied
    address and port.
    """

    pass


class TorErrorSocketFile(Exception):
    """
    hyperdome can't connect to the Tor controller using the supplied
    socket file.
    """

    pass


class TorErrorMissingPassword(Exception):
    """
    hyperdome connected to the Tor controller, but it requires a password.
    """

    pass


class TorErrorUnreadableCookieFile(Exception):
    """
    hyperdome connected to the Tor controller, but your user does not have
    permission to access the cookie file.
    """

    pass


class TorErrorAuthError(Exception):
    """
    hyperdome connected to the address and port, but can't authenticate.
    It's possible that a Tor controller isn't listening on this port.
    """

    pass


class TorErrorProtocolError(Exception):
    """
    This exception is raised if hyperdome connects to the Tor controller,
    but it isn't acting like a Tor controller (such as in Whonix).
    """

    pass


class TorTooOld(Exception):
    """
    This exception is raised if hyperdome needs to use a feature of Tor or
    stem (like stealth ephemeral onion services) but the version you have
    installed is too old.
    """

    pass


class BundledTorNotSupported(Exception):
    """
    This exception is raised if hyperdome is set to use the bundled Tor
    binary, but it's not supported on that platform, or in dev mode.
    """


class BundledTorTimeout(Exception):
    """
    This exception is raised if hyperdome is set to use the bundled Tor
    binary, but Tor doesn't finish connecting promptly.
    """


class BundledTorCanceled(Exception):
    """
    This exception is raised if hyperdome is set to use the bundled Tor
    binary, and the user cancels connecting to Tor
    """


class BundledTorBroken(Exception):
    """
    This exception is raised if hyperdome is set to use the bundled Tor
    binary, but the process seems to fail to run.
    """


@autologging.traced
@autologging.logged
class Onion(object):
    """
    Onion is an abstraction layer for connecting to the Tor control port and
    creating onion services. hyperdome supports creating onion services by
    connecting to the Tor controller and using ADD_ONION, DEL_ONION.

    settings: A Settings object. If it's not passed in, load from disk.

    bundled_connection_func: If the tor connection type is bundled, optionally
    call this function and pass in a status string while connecting to tor.
    This is necessary for status updates to reach the GUI.
    """

    __log: autologging.logging.Logger  # stop linter errors from autologging

    def __init__(self, settings):

        self.settings = settings

        self.service_id = None

        # Is bundled tor supported?
        dev_mode = getattr(sys, "hyperdome_dev_mode", False)
        self.__log.debug(f"{platform_str=}, {dev_mode=}")
        self.bundle_tor_supported = not (
            platform_str in ("Windows", "Darwin",) and dev_mode
        )

        # Set the path of the tor binary, for bundled tor
        (
            self.tor_path,
            self.tor_geo_ip_file_path,
            self.tor_geo_ipv6_file_path,
            self.obfs4proxy_file_path,
        ) = tor_paths

        # The tor process
        self.tor_proc = None

        # The Tor controller
        self.c = None

        # Start out not connected to Tor
        self.connected_to_tor = False

    def __repr__(self):
        dict_props = {
            key: self.__dict__.get(key, "NOT FOUND")
            for key in (
                "service_id",
                "bundle_tor_supported",
                "tor_proc",
                "c",
                "connected_to_tor",
            )
        }
        return f"<Onion {dict_props}>"

    def connect(
        self,
        custom_settings=False,
        config=False,
        tor_status_update_func=None,
        connect_timeout=120,
    ):

        # Either use settings that are passed in, or use them from common
        self.settings = custom_settings or self.settings

        # The Tor controller
        self.c = None

        if self.settings.get("connection_type") == "bundled":
            self.__log.info(f"{self.bundle_tor_supported=}")
            if not self.bundle_tor_supported:
                raise BundledTorNotSupported(
                    strings._("settings_error_bundled_tor_not_supported")
                )

            # Create a torrc for this session
            self.tor_data_directory = tempfile.TemporaryDirectory(dir=data_path,)
            self.__log.info(f"tor_data_directory={self.tor_data_directory.name}",)

            # Create the torrc
            torrc_template = resource_path.joinpath("torrc_template").read_text()
            self.tor_cookie_auth_file = Path(
                self.tor_data_directory.name, "cookie"
            ).resolve()
            self.tor_socks_port = get_available_port(1000, 65535)
            self.tor_torrc = Path(self.tor_data_directory.name, "torrc").resolve()

            if platform_str in ("Windows", "Darwin"):
                # Windows doesn't support unix sockets, so it must use
                # a network port.
                # macOS can't use unix sockets either because socket filenames
                # are limited to 100 chars, and the macOS sandbox forces us
                # to put the socket file in a place with a really long path.
                torrc_template += "ControlPort {{control_port}}\n"
                self.tor_control_port = get_available_port(1000, 65535)
                self.tor_control_socket = None
            else:
                # Linux and BSD can use unix sockets
                torrc_template += "ControlSocket {{control_socket}}\n"
                self.tor_control_port = None
                self.tor_control_socket = Path(
                    self.tor_data_directory.name, "control_socket"
                ).resolve()
                self.tor_control_socket.touch()
                self.__log.info(f"{self.tor_control_socket=}")

            torrc_template = torrc_template.replace(
                "{{data_directory}}", self.tor_data_directory.name
            )
            torrc_template = torrc_template.replace(
                "{{control_port}}", str(self.tor_control_port)
            )
            torrc_template = torrc_template.replace(
                "{{control_socket}}", str(self.tor_control_socket)
            )
            torrc_template = torrc_template.replace(
                "{{cookie_auth_file}}", str(self.tor_cookie_auth_file)
            )
            torrc_template = torrc_template.replace(
                "{{geo_ip_file}}", str(self.tor_geo_ip_file_path)
            )
            torrc_template = torrc_template.replace(
                "{{geo_ipv6_file}}", str(self.tor_geo_ipv6_file_path)
            )
            torrc_template = torrc_template.replace(
                "{{socks_port}}", str(self.tor_socks_port)
            )

            with self.tor_torrc.open("w",) as f:
                f.write(torrc_template)

                # Bridge support
                if self.settings.get("tor_bridges_use_obfs4"):
                    f.write(
                        f"ClientTransportPlugin obfs4 exec {self.obfs4proxy_file_path}\n"
                    )
                    f.write(resource_path.joinpath("torrc_template-obfs4").read_text())
                elif self.settings.get("tor_bridges_use_meek_lite_azure"):
                    f.write(
                        f"ClientTransportPlugin meek_lite exec {self.obfs4proxy_file_path}\n"
                    )
                    f.write(
                        resource_path.joinpath(
                            "torrc_template-meek_lite_azure"
                        ).read_text()
                    )

                if self.settings.get("tor_bridges_use_custom_bridges"):
                    if "obfs4" in self.settings.get("tor_bridges_use_custom_bridges"):
                        f.write(
                            f"ClientTransportPlugin obfs4 exec {self.obfs4proxy_file_path}\n"
                        )
                    elif "meek_lite" in self.settings.get(
                        "tor_bridges_use_" "custom_bridges"
                    ):
                        f.write(
                            f"ClientTransportPlugin meek_lite exec {self.obfs4proxy_file_path}\n"
                        )
                    f.write(self.settings.get("tor_bridges_use_custom_bridges"))
                    f.write("\nUseBridges 1")

            self.tor_torrc.chmod(0o620)

            # Execute a tor subprocess
            start_ts = time.time()
            tor_subprocess_args = [str(self.tor_path), "-f", str(self.tor_torrc)]
            self.__log.info(
                f"launching tor process with command: {' '.join(tor_subprocess_args)}"
            )
            if platform_str == "Windows":
                # In Windows, hide console window when opening tor.exe
                # subprocess
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            else:
                startupinfo = None
            self.tor_proc = subprocess.Popen(
                tor_subprocess_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
            )

            # Wait for the tor controller to start
            time.sleep(2)

            # Connect to the controller
            try:
                if platform_str in ("Windows", "Darwin"):
                    self.c = Controller.from_port(port=self.tor_control_port)
                    self.c.authenticate()
                else:
                    self.c = Controller.from_socket_file(
                        path=str(self.tor_control_socket)
                    )
                    self.c.authenticate()
            except (TypeError, stem.SocketError):
                raise
            except Exception as e:
                raise BundledTorBroken(
                    strings._("settings_error_bundled_tor_broken").format(e.args[0])
                )

            while True:
                try:
                    res = self.c.get_info("status/bootstrap-phase")
                except SocketClosed:
                    raise BundledTorCanceled()

                res_parts = shlex.split(res)
                progress = res_parts[2].split("=")[1]
                summary = res_parts[4].split("=")[1]

                # "\033[K" clears the rest of the line
                print(
                    "{}: {}% - {}{}".format(
                        strings._("connecting_to_tor"), progress, summary, "\033[K"
                    ),
                    end="\r",
                )

                if callable(tor_status_update_func) and not tor_status_update_func(
                    progress, summary
                ):
                    # If the dialog was canceled, stop connecting to Tor
                    self.__log.warning(
                        "tor_status_update_func returned "
                        "false, canceling connecting to Tor",
                    )
                    return False

                if summary == "Done":
                    print("")
                    break
                time.sleep(0.5)

                # If using bridges, it might take a bit longer to connect to
                # Tor
                if (
                    self.settings.get("tor_bridges_use_custom_bridges")
                    or self.settings.get("tor_bridges_use_obfs4")
                    or self.settings.get("tor_bridges_use_meek_lite_azure")
                ):
                    # Only override timeout if a custom timeout has not been
                    # passed in
                    if connect_timeout == 120:
                        connect_timeout = 150
                if time.time() - start_ts > connect_timeout:
                    try:
                        self.tor_proc.terminate()
                        raise BundledTorTimeout(
                            strings._("settings_error_bundled_tor_timeout")
                        )
                    except FileNotFoundError:
                        self.__log.warning("", exc_info=True)
                        pass

        elif self.settings.get("connection_type") == "automatic":
            # Automatically try to guess the right way to connect to Tor
            # Browser

            # Try connecting to control port
            found_tor = False

            # If the TOR_CONTROL_PORT environment variable is set, use that
            env_port = os.environ.get("TOR_CONTROL_PORT")
            if env_port:
                self.c = Controller.from_port(port=int(env_port))
                found_tor = True

            else:
                # Otherwise, try default ports for Tor Browser, Tor Messenger,
                # and system tor
                try:
                    ports = [9151, 9153, 9051]
                    for port in ports:
                        self.c = Controller.from_port(port=port)
                        found_tor = True
                except SocketError:
                    pass

                # If this still didn't work, try guessing the default socket
                # file path
                socket_file_path = ""
                if not found_tor:
                    if platform_str == "Darwin":
                        socket_file_path = os.path.expanduser(
                            "~/Library/Application Support/"
                            "TorBrowser-Data/Tor/control.socket"
                        )
                    try:
                        self.c = Controller.from_socket_file(path=socket_file_path)
                        found_tor = True
                    except (AttributeError, stem.SocketError):
                        pass

            # If connecting to default control ports failed, so let's try
            # guessing the socket file name next
            if not found_tor:
                try:
                    if platform_str in ("Linux", "BSD"):
                        socket_file_path = (
                            f"/run/user/{os.geteuid()}/Tor/" "control.socket"
                        )
                    elif platform_str == "Darwin":
                        socket_file_path = (
                            f"/run/user/{os.geteuid()}/Tor/" "control.socket"
                        )
                    else:  # platform_str == 'Windows':
                        # Windows doesn't support unix sockets
                        raise TorErrorAutomatic(strings._("settings_error_automatic"))

                    self.c = Controller.from_socket_file(path=socket_file_path)

                except (TorErrorAutomatic, stem.SocketError):
                    raise TorErrorAutomatic(strings._("settings_error_automatic"))

            # Try authenticating
            try:
                self.c.authenticate()
            except stem.connection.AuthenticationFailure:
                raise TorErrorAutomatic(strings._("settings_error_automatic"))

        else:
            # Use specific settings to connect to tor

            # Try connecting
            try:
                if self.settings.get("connection_type") == "control_port":
                    self.c = Controller.from_port(
                        address=self.settings.get("control_port_address"),
                        port=self.settings.get("control_port_port"),
                    )
                elif self.settings.get("connection_type") == "socket_file":
                    self.c = Controller.from_socket_file(
                        path=self.settings.get("socket_file_path")
                    )
                else:
                    raise TorErrorInvalidSetting(strings._("settings_error_unknown"))

            except (TorErrorInvalidSetting, stem.SocketError):
                if self.settings.get("connection_type") == "control_port":
                    raise TorErrorSocketPort(
                        strings._("settings_error_socket_port").format(
                            self.settings.get("control_port_address"),
                            self.settings.get("control_port_port"),
                        )
                    )
                else:
                    raise TorErrorSocketFile(
                        strings._("settings_error_socket_file").format(
                            self.settings.get("socket_file_path")
                        )
                    )

            # Try authenticating
            try:
                if self.settings.get("auth_type") == "no_auth":
                    self.c.authenticate()
                elif self.settings.get("auth_type") == "password":
                    self.c.authenticate(self.settings.get("auth_password"))
                else:
                    raise TorErrorInvalidSetting(strings._("settings_error_unknown"))

            except MissingPassword:
                raise TorErrorMissingPassword(
                    strings._("settings_error_missing_password")
                )
            except UnreadableCookieFile:
                raise TorErrorUnreadableCookieFile(
                    strings._("settings_error_unreadable_cookie_file")
                )
            except AuthenticationFailure:
                raise TorErrorAuthError(
                    strings._("settings_error_auth").format(
                        self.settings.get("control_port_address"),
                        self.settings.get("control_port_port"),
                    )
                )

        # If we made it this far, we should be connected to Tor
        self.connected_to_tor = True

        # Get the tor version
        self.tor_version = self.c.get_version().version_str
        self.__log.info(f"Connected to tor {self.tor_version}")

        # Do the versions of stem and tor that I'm using support ephemeral
        # onion services?
        list_ephemeral_hidden_services = getattr(
            self.c, "list_ephemeral_hidden_services", None
        )
        self.supports_ephemeral = (
            callable(list_ephemeral_hidden_services) and self.tor_version >= "0.2.7.1"
        )

        # Does this version of Tor support next-gen ('v3') onions?
        # Note, this is the version of Tor where this bug was fixed:
        # https://trac.torproject.org/projects/tor/ticket/28619
        self.supports_v3_onions = self.tor_version >= Version("0.3.5.7")

    def is_authenticated(self):
        """
        Returns whether Tor connection is still working.
        """
        return self.c is not None and self.c.is_authenticated()

    def start_onion_service(self, port):
        """
        Start a onion service on port 80, pointing to the given port, and
        return the onion hostname.
        """

        self.auth_string = None
        if not self.supports_ephemeral:
            raise TorTooOld(strings._("error_ephemeral_not_supported"))
        if not self.supports_v3_onions:
            raise TorTooOld("Hyperdome requires v3 onion support")

        print(strings._("config_onion_service").format(int(port)))

        if self.settings.get("private_key"):
            key_content = self.settings.get("private_key")
            key_type = "ED25519-V3"
        else:
            key_type = "NEW"
            key_content = "ED25519-V3"

        debug_message = f"{key_type=}"
        if key_type == "NEW":
            debug_message += f", {key_content=}"
        self.__log.debug(f"{debug_message}")
        await_publication = True
        try:
            res = self.c.create_ephemeral_hidden_service(
                {80: port},
                await_publication=await_publication,
                key_type=key_type,
                key_content=key_content,
                timeout=10,
            )
        except ProtocolError as e:
            raise TorErrorProtocolError(
                strings._("error_tor_protocol_error").format(e.args[0])
            )

        self.service_id = res.service_id
        onion_host = self.service_id + ".onion"

        # A new private key was generated and is in the Control port response.
        if self.settings.get("save_private_key") and not self.settings.get(
            "private_key"
        ):
            self.settings.set("private_key", res.private_key)

        if onion_host is not None:
            self.settings.save()
            return onion_host
        else:
            raise TorErrorProtocolError(strings._("error_tor_protocol_error_unknown"))

    def cleanup(self, stop_tor=True):
        """
        Stop onion services that were created earlier. If there's a tor
        subprocess running, kill it.
        """

        # Cleanup the ephemeral onion services, if we have any
        if self.c:
            onions = self.c.list_ephemeral_hidden_services()
            for onion in onions:
                try:
                    self.__log.info(f"trying to remove onion {onion}")
                    self.c.remove_ephemeral_hidden_service(onion)
                except stem.ControllerError:
                    self.__log.warning(
                        f"could not remove onion " "{onion}, continuing.", exc_info=True
                    )
        self.service_id = None

        if stop_tor:
            # Stop tor process
            if self.tor_proc:
                self.tor_proc.terminate()
                time.sleep(0.2)
                if not self.tor_proc.poll():
                    self.tor_proc.kill()
                self.tor_proc = None

            # Reset other Onion settings
            self.connected_to_tor = False

            try:
                # Delete the temporary tor data directory
                self.tor_data_directory.cleanup()
            except AttributeError:
                self.__log.info("temp directory was already deleted")
                # Skip if cleanup was somehow run before connect
                pass
            except PermissionError:
                self.__log.warning("couldn't clean temp directory", exc_info=True)
                # Skip if the directory is still open (#550)
                # TODO: find a better solution
                pass

    def get_tor_socks_port(self):
        """
        Returns a (address, port) tuple for the Tor SOCKS port
        """

        if self.settings.get("connection_type") == "bundled":
            return ("127.0.0.1", self.tor_socks_port)
        elif self.settings.get("connection_type") == "automatic":
            return ("127.0.0.1", 9150)
        else:
            return (self.settings.get("socks_address"), self.settings.get("socks_port"))
