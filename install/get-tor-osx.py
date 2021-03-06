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
import inspect
import os
import sys
import hashlib
import shutil
import subprocess
import requests


def main():
    dmg_url = (
        "https://archive.torproject.org/tor-package-archive"
        "/torbrowser/9.0.7/TorBrowser-9.0.7-osx64_en-US.dmg"
    )
    asc_url = (
        "https://archive.torproject.org/tor-package-archive"
        "/torbrowser/9.0.7/TorBrowser-9.0.7-osx64_en-US.dmg.asc"
    )
    dmg_filename = "TorBrowser-9.0.7-osx64_en-US.dmg"

    # Build paths
    root_path = os.path.dirname(
        os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    )
    working_path = os.path.join(root_path, "build", "tor")
    dmg_tor_path = os.path.join(
        "/Volumes", "Tor Browser", "Tor Browser.app", "Contents"
    )
    dmg_path = os.path.join(working_path, dmg_filename)
    dist_path = os.path.join(root_path, "dist", "Hyperdome.app", "Contents")

    # Make sure the working folder exists
    if not os.path.exists(working_path):
        os.makedirs(working_path)

    # Make sure the zip is downloaded
    if not os.path.exists(dmg_path):
        print("Downloading {}".format(dmg_url))
        r = requests.get(dmg_url)
        open(dmg_path, "wb").write(r.content)
    else:
        dmg_data = open(dmg_path, "rb").read()

    print("Downloading {}".format(asc_url))
    asc_data = requests.get(asc_url).content

    # TODO: Verify by asc

    # Mount the dmg, copy data to the working path
    subprocess.call(["hdiutil", "attach", dmg_path])

    # Make sure Resources/tor exists before copying files
    if os.path.exists(os.path.join(dist_path, "Resources", "Tor")):
        shutil.rmtree(os.path.join(dist_path, "Resources", "Tor"))
    os.makedirs(os.path.join(dist_path, "Resources", "Tor"))
    if os.path.exists(os.path.join(dist_path, "MacOS", "Tor")):
        shutil.rmtree(os.path.join(dist_path, "MacOS", "Tor"))
    os.makedirs(os.path.join(dist_path, "MacOS", "Tor"))

    # Modify the tor script to adjust the path
    tor_script = open(
        os.path.join(dmg_tor_path, "Resources", "TorBrowser", "Tor", "tor"), "r"
    ).read()
    tor_script = tor_script.replace("../../../MacOS/Tor", "../../MacOS/Tor")
    open(os.path.join(dist_path, "Resources", "Tor", "tor"), "w").write(tor_script)

    # Copy into dist
    shutil.copyfile(
        os.path.join(dmg_tor_path, "Resources", "TorBrowser", "Tor", "geoip"),
        os.path.join(dist_path, "Resources", "Tor", "geoip"),
    )
    shutil.copyfile(
        os.path.join(dmg_tor_path, "Resources", "TorBrowser", "Tor", "geoip6"),
        os.path.join(dist_path, "Resources", "Tor", "geoip6"),
    )
    os.chmod(os.path.join(dist_path, "Resources", "Tor", "tor"), 0o755)
    shutil.copyfile(
        os.path.join(dmg_tor_path, "MacOS", "Tor", "tor.real"),
        os.path.join(dist_path, "MacOS", "Tor", "tor.real"),
    )
    shutil.copyfile(
        os.path.join(dmg_tor_path, "MacOS", "Tor", "libevent-2.1.6.dylib"),
        os.path.join(dist_path, "MacOS", "Tor", "libevent-2.1.6.dylib"),
    )
    os.chmod(os.path.join(dist_path, "MacOS", "Tor", "tor.real"), 0o755)
    # obfs4proxy binary
    shutil.copyfile(
        os.path.join(dmg_tor_path, "MacOS", "Tor", "PluggableTransports", "obfs4proxy"),
        os.path.join(dist_path, "Resources", "Tor", "obfs4proxy"),
    )
    os.chmod(os.path.join(dist_path, "Resources", "Tor", "obfs4proxy"), 0o755)

    # Eject dmg
    subprocess.call(["diskutil", "eject", "/Volumes/Tor Browser"])


if __name__ == "__main__":
    main()
