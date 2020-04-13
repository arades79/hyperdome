# -*- coding: utf-8 -*-
"""
Hyperdome

Copyright (C) 2019-2020 Skyelar Craver <scravers@protonmail.com>
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
import flask_sqlalchemy
from flask import Flask, cli
from ..common import common

# Stub out flask's show_server_banner function, to avoiding showing
# warnings that are not applicable to hyperdome
def stubbed_show_server_banner(env, debug, app_import_path, eager_loading):
    pass

cli.show_server_banner = stubbed_show_server_banner

# The flask app
app = Flask(
    __name__,
    static_folder=common.get_resource_path("static"),
    template_folder=common.get_resource_path("templates"),
)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{common.get_resource_path("hyperdome_server.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = flask_sqlalchemy.SQLAlchemy(app)


