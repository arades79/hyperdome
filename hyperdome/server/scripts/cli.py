# -*- coding: utf-8 -*-
"""
Hyperdome

Copyright (C) 2019 - 2020 Skyelar Craver <scravers@protonmail.com>
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
from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PublicKey
from cryptography.hazmat.primitives.serialization import (
    load_ssh_public_key,
    load_der_public_key,
    load_pem_public_key,
)
from hyperdome.server import main

version = "0.2.0"  # TODO: import version from pyproject.toml


@click.group(invoke_without_command=True)
@click.option("--debug", "-d", is_flag=True)
@click.version_option(version, prog_name="Hyperdome Server")
@click.pass_context
def admin(ctx, debug):
    if ctx.invoked_subcommand is not None:
        return
    if debug:
        sys.onionshare_dev_mode = True

    main()


@admin.command()
@click.option(
    "--import",
    "-i",
    "import_",
    type=click.File(),
    multiple=True,
    help="import public key from a file (filename used as NAME)",
)
@click.argument("counselors", nargs=-1)
def add(import_, counselors):
    """Add new counselors in NAME=PUBLIC_KEY format to server database"""
    counselors += tuple(f"{file.name}={file.read()}" for file in import_)
    counselors = dict(counselor.strip(",").split("=") for counselor in counselors)
    [
        click.echo(f"counselor {name} added with public key: {pub_key}")
        for name, pub_key in counselors.items()
    ]


@admin.command()
@click.confirmation_option(prompt="are you sure you want to remove these users?")
@click.option("--pubkey", "-k", multiple=True, help="delete counselor by public key")
@click.option(
    "--file",
    "-f",
    type=click.File(),
    multiple=True,
    help="delete counselor by file used to import",
)
@click.option("--all", "all_", is_flag=True, help="delete entire counselor database")
@click.argument("names", nargs=-1)
def remove(pubkey, file, all_, names):
    """remove counselor NAMES from server database"""
    if all_:
        click.confirm(
            "this will remove all counselors from the database\n"
            "Are you really sure this is what you want?",
            abort=True,
        )
        click.echo("all counselors deleted")

    [click.echo(f"found counselor with key: {key}") for key in pubkey]
    [click.echo(f"found counselor from file {f.name}") for f in file]
    [click.echo(f"counselor removed: {name.strip(',')}") for name in names]


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
    click.confirm(
        "This will erase all active settings!\n"
        "It is recommended you first backup your current settings with --export\n"
        "Set all configuations to default?",
        abort=True,
    )
    click.echo("All settings changed to defaults")
    ctx.exit()


@admin.command()
@click.option(
    "--import",
    "-i",
    is_eager=True,
    type=click.File(),
    expose_value=False,
    help="populate config from a file",
    callback=load_config,
)
@click.option(
    "--export",
    "-e",
    is_eager=True,
    expose_value=False,
    type=click.File("w"),
    help="write existing configuration to a file",
    callback=save_config,
)
@click.option(
    "--default",
    "-d",
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
    """change settings in KEY=VALUE format or import/export config file"""

    [click.echo(f"{setting} set to default") for setting in default]
    settings = dict(setting.strip(",").split("=") for setting in settings)
    [click.echo(f"set {key} to {val}") for key, val in settings.items()]
    # need to commit these settings


if __name__ == "__main__":
    admin()
