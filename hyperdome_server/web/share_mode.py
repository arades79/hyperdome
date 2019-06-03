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

login_manager = LoginManager()


def get_user_class_from_db_and_bcrypt(db, bcrypt):
    class User(db.Model, UserMixin):
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
            return bcrypt.check_password_hash(self._password,
                                                  plaintext)
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
        web.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///./therapists.db'
        self.db = SQLAlchemy(web.app)
        self.define_routes()

        self.bcrypt = Bcrypt(web.app)
        login_manager.init_app(web.app)
        login_manager.login_view = "therapist_signin"
        login_manager.session_protection = None
        self.therapists_available = []
        self.connected_therapist = dict()
        self.connected_guest = dict()
        self.pending_messages = dict()
        self.user_class = get_user_class_from_db_and_bcrypt(self.db, self.bcrypt)

    def define_routes(self):

        @self.web.app.before_request
        def before_request():
            user = load_user(request.headers.get("username", ""))
            if user and user.is_correct_password(
                    request.headers.get("password", "")):
                login_user(user)

        @login_manager.user_loader
        def load_user(username):
            self.db.create_all()
            return self.user_class.query.filter(self.user_class.username == username).first()

        @self.web.app.errorhandler(Exception)
        def unhandled_exception(e):
            e_str = ''.join(traceback.format_exception(type(e),
                                                       e,
                                                       e.__traceback__))
            print(e_str)
            return e_str

        @self.web.app.route("/request_therapist", methods=['POST'])
        def request_therapist():
            guest_id = request.form['guest_id']
            if self.therapists_available:
                chosen_therapist = random.choice(self.therapists_available)
                self.therapists_available.remove(chosen_therapist)
                self.connected_therapist[guest_id] = chosen_therapist.username
                self.connected_guest[chosen_therapist.username] = guest_id
                return chosen_therapist.username
            return ''

        @login_required
        @self.web.app.route("/therapy_complete", methods=['POST'])
        def therapy_complete():
            self.connected_therapist.pop(
                self.connected_guest[current_user.username])
            self.connected_guest.pop(current_user.username)
            self.therapists_available.append(current_user)

        @self.web.app.route("/therapist_signout", methods=["POST"])
        @login_required
        def therapist_signout():
            user = load_user(request.form['username'])
            logout_user(user)
            self.therapists_available.remove(user)

        @self.web.app.route("/therapist_signup", methods=["POST"])
        def therapist_signup():
            if request.form.get('masterkey', "") == "megumin":
                if load_user(request.form['username']):
                    return "Username already exists"
                user = self.user_class(username=request.form['username'],
                                       password=request.form['password'])
                self.db.session.add(user)
                self.db.session.commit()
                return "Success"
            return abort(401)

        @self.web.app.route("/therapist_signin", methods=["POST"])
        def therapist_signin():
            # TODO authenticate
            user = load_user(request.form['username'])
            self.therapists_available.append(user)
            return "Success"

        @self.web.app.route("/generate_guest_id")
        def generate_guest_id():
            return binascii.b2a_hex(os.urandom(15))

        @self.web.app.route("/message_from_therapist", methods=['POST'])
        @login_required
        def message_from_therapist():
            if current_user.username not in self.connected_guest:
                return abort(401)
            message = request.form['message']

            guest_id = self.connected_guest[current_user.username]
            self.pending_messages[guest_id] = (
                self.pending_messages.get(
                    guest_id, "") + message + "\n")
            return "Success"

        @self.web.app.route("/message_from_user", methods=['POST'])
        def message_from_user():
            message = request.form['message']
            guest_id = request.form['guest_id']
            therapist_username = self.connected_therapist[guest_id]
            self.pending_messages[therapist_username] = (
                self.pending_messages.get(therapist_username, "")
                + message + "\n")
            return "Success"

        @self.web.app.route("/collect_guest_messages")
        def collect_guest_messages():
            guest_id = request.form['guest_id']
            return self.pending_messages.pop(guest_id, "")

        @self.web.app.route("/collect_therapist_messages")
        @login_required
        def collect_therapist_messages():
            therapist_username = current_user.username
            return self.pending_messages.pop(therapist_username, "")
