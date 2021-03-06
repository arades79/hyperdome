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
    exe_url = "https://archive.torproject.org/tor-package-archive/torbrowser/9.0.7/torbrowser-install-9.0.7_en-US.exe"
    asc_url = "https://archive.torproject.org/tor-package-archive/torbrowser/9.0.7/torbrowser-install-9.0.7_en-US.exe.asc"
    exe_filename = "torbrowser-install-9.0.7_en-US.exe"

    # Build paths
    root_path = os.path.dirname(
        os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
    )
    working_path = os.path.join(os.path.join(root_path, "build"), "tor")
    exe_path = os.path.join(working_path, exe_filename)

    dist_path = os.path.join(
        os.path.join(os.path.join(root_path, "dist"), "hyperdome"), "tor"
    )

    # Make sure the working folder exists
    if not os.path.exists(working_path):
        os.makedirs(working_path)

    # Make sure the zip is downloaded
    if not os.path.exists(exe_path):
        print("Downloading {}".format(exe_url))
        r = requests.get(exe_url)
        open(exe_path, "wb").write(r.content)
    else:
        exe_data = open(exe_path, "rb").read()

    print("Downloading {}".format(asc_url))
    asc_data = requests.get(asc_url).content

    # TODO: verify sig from .asc

    # Extract the bits we need from the exe
    cmd = [
        "7z",
        "e",
        "-y",
        exe_path,
        r"Browser\TorBrowser\Tor",
        "-o%s" % os.path.join(working_path, "Tor"),
    ]
    cmd2 = [
        "7z",
        "e",
        "-y",
        exe_path,
        r"Browser\TorBrowser\Data\Tor\geoip*",
        "-o%s" % os.path.join(working_path, "Data"),
    ]
    subprocess.Popen(cmd).wait()
    subprocess.Popen(cmd2).wait()

    # Copy into dist
    if os.path.exists(dist_path):
        shutil.rmtree(dist_path)
    os.makedirs(dist_path)
    shutil.copytree(os.path.join(working_path, "Tor"), os.path.join(dist_path, "Tor"))
    shutil.copytree(
        os.path.join(working_path, "Data"), os.path.join(dist_path, "Data", "Tor")
    )


if __name__ == "__main__":
    main()
