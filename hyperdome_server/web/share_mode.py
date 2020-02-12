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
import os
from flask import request, abort
from flask_login import (login_user, logout_user, LoginManager,
                         UserMixin, login_required, current_user)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.hybrid import hybrid_property
from flask_bcrypt import Bcrypt
import random
import binascii
import traceback
import json

login_manager = LoginManager()


def get_user_class_from_db_and_bcrypt(db, bcrypt):
    class User(db.Model):
        __tablename__ = 'users'
        id = db.Column(db.Integer, primary_key=True,
                       autoincrement=True)
        username = db.Column(db.String(64), unique=True)
        _password = db.Column(db.String(128))

        @hybrid_property
        def password(self):
            return self._password

        @password.setter
        def password(self, plaintext):
            self._password = bcrypt.generate_password_hash(plaintext)

        def is_correct_password(self, plaintext):
            return bcrypt.check_password_hash(self._password, plaintext)
    return User


class ShareModeWeb(object):
    """
    All of the web logic for share mode
    """

    def __init__(self, common, web):
        self.common = common
        self.common.log('ShareModeWeb', '__init__')

        self.web = web

        web.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        web.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///./counselors.db'
        self.db = SQLAlchemy(web.app)
        self.define_routes()

        self.bcrypt = Bcrypt(web.app)
        login_manager.init_app(web.app)
        login_manager.login_view = "counselor_signin"
        login_manager.session_protection = None
        self.counselors_available = dict()
        self.active_chat_user_map = dict()
        self.pending_messages = dict()
        self.user_class = get_user_class_from_db_and_bcrypt(self.db,
                                                            self.bcrypt)

        self.info = {'name':'hyperdome',
                     'version': self.common.version,
                     'online': str(len(self.counselors_available))}



    def define_routes(self):

        @self.web.app.errorhandler(Exception)
        def unhandled_exception(e):
            e_str = ''.join(traceback.format_exception(type(e),
                                                       e,
                                                       e.__traceback__))
            print(e_str)
            return "Exception raised", 500

        @self.web.app.route("/probe")
        def probe():
            self.info['online'] = str(len(self.counselors_available))
            return json.dumps(self.info)

        @self.web.app.route("/request_counselor", methods=['POST'])
        def request_counselor():
            guest_id = request.form['guest_id']
            counselors = [counselor for counselor in self.counselors_available if self.counselors_available[counselor] > 0]
            if not counselors:
                return ''
            chosen_counselor = random.choice(counselors)
            self.counselors_available[chosen_counselor] -= 1
            self.active_chat_user_map[guest_id] = chosen_counselor
            self.active_chat_user_map[chosen_counselor] = guest_id
            return 'Success'

        @self.web.app.route("/counseling_complete", methods=['POST'])
        def counseling_complete():
            sid = request.form['user_id']
            if sid not in self.active_chat_user_map:
                return 'no active chat', 404
            other_user = self.active_chat_user_map[sid]
            self.active_chat_user_map.pop(sid)
            self.active_chat_user_map.pop(other_user)
            counselor = sid if sid in self.counselors_available else other_user
            self.counselors_available[counselor] += 1
            return 'Chat Ended'


        @self.web.app.route("/counselor_signout", methods=["POST"])
        def counselor_signout():
            sid = request.form['user_id']
            self.counselors_available.pop(sid)

        @self.web.app.route("/counselor_signin")
        def counselor_signin():
            # TODO authenticate
            # user = load_user(request.form['username'])
            sid = binascii.b2a_hex(os.urandom(15)).decode('utf-8')
            self.counselors_available[sid] = 1 # will use capacity variable for this later
            return sid

        @self.web.app.route("/generate_guest_id")
        def generate_guest_id():
            # TODO check for collisions
            return binascii.b2a_hex(os.urandom(15)).decode('utf-8')

        @self.web.app.route("/send_message", methods=['POST'])
        def message_from_user():
            message = request.form['message']
            user_id = request.form['user_id']
            if user_id not in self.active_chat_user_map:
                return "no chat", 404
            other_user = self.active_chat_user_map[user_id]
            self.pending_messages[other_user] += f"{message}\n"
            return "Success"

        @self.web.app.route("/collect_messages", methods=['GET'])
        def collect_messages():
            guest_id = request.form['user_id']
            return self.pending_messages.pop(guest_id, "")
