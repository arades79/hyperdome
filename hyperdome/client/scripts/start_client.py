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

import logging

from autologging import install_traced_noop
import click

logging.addLevelName(1000, "OFF")


@click.command()
@click.option(
    "--log-level",
    "-l",
    "log_level",
    type=click.Choice(
        ["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "OFF"], case_sensitive=False
    ),
    default="ERROR",
    help="override logging level for this run",
    show_default=True,
)
@click.option(
    "--log-file",
    "log_file",
    type=click.Path(
        exists=False,
    ),
    help="file to to write logs to for this run instead of stdout",
    default=None,
)
def start(log_level, log_file):
    if log_level != "TRACE":
        install_traced_noop()
    logging.basicConfig(
        level=log_level,
        filename=log_file,
        format="%(levelname)s\t%(name)s.%(funcName)s:%(lineno)d:\n\t%(message)s",
    )

    # hyperdome imports are done here so noop traced is used
    from ...common.common import version
    from ..main import main

    click.echo(f"Hyperdome {version} | https://hyperdome.org")
    main()
