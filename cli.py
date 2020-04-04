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

import click
import sys
import os
import hyperdome_server
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PublicKey
from cryptography.hazmat.primitives.serialization import (
    load_ssh_public_key,
    load_der_public_key,
    load_pem_public_key,
)

version = "0.2"


@click.group(invoke_without_command=True)
@click.option('--debug', '-d', is_flag=True)
@click.version_option(version, prog_name="Hyperdome Server")
@click.pass_context
def admin(ctx, debug):
    if ctx.invoked_subcommand is not None:
        return
    if debug:
        # TODO there must be a cleaner way to do this
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        sys.onionshare_dev_mode = True
    hyperdome_server.main()


@admin.command()
@click.option(
    "--file", is_flag=True, help="import public key from a file"
)
@click.argument("pub_keys", nargs=-1)
def add(file, pub_keys):
    """Add new counselor public keys to server database"""
    if file:
        click.echo("loading keys from file...")
        pub_keys = [open(f, "r").read() for f in pub_keys]
    [click.echo(f"counselor added with public key: {pub_key}") for pub_key in pub_keys]


@admin.command()
@click.confirmation_option(prompt="are you sure you want to remove these users?")
@click.argument("names", nargs=-1)
def remove(names):
    """remove counselors from server database"""
    [click.echo(f"counselor removed: {name}") for name in names]


if __name__ == "__main__":
    admin()
