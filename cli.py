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
import json
import hyperdome_server
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PublicKey
from cryptography.hazmat.primitives.serialization import (
    load_ssh_public_key,
    load_der_public_key,
    load_pem_public_key,
)


version = "0.2"


@click.group(invoke_without_command=True)
@click.option("--debug", "-d", is_flag=True)
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
@click.option("--file", is_flag=True, help="import public key from a file")
@click.argument("counselors", nargs=-1)
def add(file, counselors):
    """Add new counselor public keys to server database"""
    if file:
        click.echo("loading keys from file...")
        counselors = [open(f, "r").read() for f in counselors]
    [click.echo(f"counselor added with public key: {pub_key}") for pub_key in pub_keys]


@admin.command()
@click.confirmation_option(prompt="are you sure you want to remove these users?")
@click.argument("names", nargs=-1)
def remove(names):
    """remove counselors from server database"""
    [click.echo(f"counselor removed: {name}") for name in names]


def load_config(ctx, param, value):
    if not value:
        return
    click.echo(f"settings loaded from {value.name}")
    ctx.exit()


def save_config(ctx, param, value):
    if not value:
        return
    click.echo(f"settings stored to {value.name}")
    ctx.exit()


def default_config(ctx, param, value):
    if not value:
        return
    try:
        click.confirm(
            "This will erase all active settings!\n"
            "It is recommended you first backup your current settings with --export\n"
            "Set all configuations to default?",
            abort=True,
        )
        click.echo("All settings changed to defaults")
    except click.Abort:
        click.echo("operation cancelled")
    finally:
        ctx.exit()


@admin.command()
@click.option(
    "--import",
    "-i",
    is_eager=True,
    type=click.File(),
    help="populate config from a file",
    callback=load_config,
)
@click.option(
    "--export",
    "-e",
    is_eager=True,
    type=click.File("w"),
    help="write existing configuration to a file",
    callback=save_config,
)
@click.option(
    "--default",
    type=str,
    multiple=True,
    help="set the named setting to its default value",
)
@click.option(
    "--all_defaults",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    help="set all config values to application defaults",
    callback=default_config,
)
@click.argument("settings", nargs=-1)
def config(default, settings):
    """set settings via key=value pairs or import/export config file"""

    (click.echo(f"{setting} set to default") for setting in default)
    settings = dict(setting.split("=") for setting in settings)
    # need to commit these settings


if __name__ == "__main__":
    admin()
