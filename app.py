from flask import (Flask, Request, request, render_template,
                   make_response, flash, redirect, url_for, abort)
from flask_login import (login_user, logout_user, LoginManager,
                         UserMixin, login_required)
from flask_wtf import FlaskForm
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.hybrid import hybrid_property
from flask_bcrypt import Bcrypt, generate_password_hash
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
import random


app = Flask(__name__)
app.config['SECRET_KEY'] = 'megumin'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///./therapists.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
User = UserMixin
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "therapist_signin"
therapists_online = []


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
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


@login_manager.user_loader
def load_user(username):
    return User.query.filter(User.username == username).first()


@app.route("/request_therapist", methods=['GET'])
def request_therapist():
    return random.choice([therapist.username
                          for therapist in therapists_online])


def try_login(username, password):
    user = load_user(username)
    if user:
        return user.is_correct_password(password)


@app.route("/therapist_signout", methods=["POST"])
def therapist_signout():
    user = load_user(request.form['username'])
    logout_user(user)
    therapists_online.remove(user)


@app.route("/therapist_signup", methods=["POST"])
def therapist_signup():
    if request.form.get('masterkey', "") == "megumin":
        if load_user(request.form['username']):
            return "Username already exists"
        user = User(username=request.form['username'],
                    password=request.form['password'])
        db.session.add(user)
        db.session.commit()
        return "Success"
    return abort(401)


@app.route("/therapist_signin", methods=['GET', 'POST'])
def therapist_signin():
    if request.method == "POST":
        user = load_user(request.form['username'])
        if user:
            if user.is_correct_password(request.form['password']):
                login_user(user, remember=True)
                therapists_online.append(user)
                return "Success"
            return "Incorrect password"
        return "User does not exist"


@app.route("/therapist_view")
@login_required
def therapist_view():
    return "WHat"
