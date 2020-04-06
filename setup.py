#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OnionShare | https://onionshare.org/

Copyright (C) 2014-2018 Micah Lee <micah@micahflee.com>

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

import os
import sys
import platform
from distutils.core import setup


def file_list(path):
    files = []
    for filename in os.listdir(path):
        if os.path.isfile(os.path.join(path, filename)):
            files.append(os.path.join(path, filename))
    return files


version = open("share/version.txt").read().strip()
description = """The safest place to reach out"""
long_description = (
    description
    + "\n\n"
    + (
        """Hyperdome is an asymmetrical chat application designed to have distributed and domain specific servers.
        Users connect completely anonymously to the server and will be paired with whatever that server determines is qualified counsel.
        College campuses could provide safe mental health services with no fear.
        Legal offices can provide counseling to prospective clients with everything on the table.
        Hyperdome provides a simple server and client that any entity can implement to give some set of guests access to a verified list of people."""
    )
)
author = "Skyelar Ceaver"
author_email = "scravers@protonmail.com"
url = "https://github.com/arades79/hyperdome"
license = "GPL v3"
keywords = "onion, hyperdome, tor, anonymous, web server, therapy, counseling"
classifiers = [
    "Programming Language :: Python :: 3",
    "Framework :: Flask",
    "Topic :: Communications :: Wellness",
    "Topic :: Security :: Cryptography",
    "License :: OSI Approved :: GNU General Public License v3 or later",
    "Intended Audience :: End Users/Desktop",
    "Operating System :: OS Independent",
    "Environment :: Web Environment",
]
data_files = [
    (os.path.join(sys.prefix, "share/applications"), ["install/onionshare.desktop"]),
    (os.path.join(sys.prefix, "share/metainfo"), ["install/onionshare.appdata.xml"]),
    (os.path.join(sys.prefix, "share/pixmaps"), ["install/onionshare80.xpm"]),
    (os.path.join(sys.prefix, "share/onionshare"), file_list("share")),
    (os.path.join(sys.prefix, "share/onionshare/images"), file_list("share/images")),
    (os.path.join(sys.prefix, "share/onionshare/locale"), file_list("share/locale")),
    (
        os.path.join(sys.prefix, "share/onionshare/templates"),
        file_list("share/templates"),
    ),
    (
        os.path.join(sys.prefix, "share/onionshare/static/css"),
        file_list("share/static/css"),
    ),
    (
        os.path.join(sys.prefix, "share/onionshare/static/img"),
        file_list("share/static/img"),
    ),
    (
        os.path.join(sys.prefix, "share/onionshare/static/js"),
        file_list("share/static/js"),
    ),
]
if platform.system() != "OpenBSD":
    data_files.append(
        (
            "/usr/share/nautilus-python/extensions/",
            ["install/scripts/onionshare-nautilus.py"],
        )
    )

setup(
    name="hyperdome",
    version=version,
    description=description,
    long_description=long_description,
    author=author,
    author_email=author_email,
    maintainer=author,
    maintainer_email=author_email,
    url=url,
    license=license,
    keywords=keywords,
    classifiers=classifiers,
    packages=["hyperdome_server.web", "hyperdome_client",],
    include_package_data=True,
    scripts=["install/scripts/hyperdome_client", "install/scripts/hyperdome_server", "install/scripts/cli.py"],
    data_files=data_files,
)
