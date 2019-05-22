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

# Load onionshare module and resources from the source code tree
import os
import sys
#TODO there must be a cleaner way to do this
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.onionshare_dev_mode = True

import hyperdome_server

def main():
    hyperdome_server.main()


if __name__ == "__main__":
    main()
