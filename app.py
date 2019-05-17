from flask import (Flask, Request, request, render_template,
                   make_response, flash, redirect, url_for, abort)
from flask_login import (login_user, logout_user, LoginManager,
                         UserMixin, login_required, current_user)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.hybrid import hybrid_property
from flask_bcrypt import Bcrypt
import random
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = 'megumin'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///./therapists.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "therapist_signin"
login_manager.session_protection = None
therapists_available = []
connected_therapist = dict()
connected_guest = dict()
pending_messages = dict()


@app.before_request
def before_request():
    user = load_user(request.headers.get("username", ""))
    if user and user.is_correct_password(request.headers.get("password", "")):
        login_user(user)


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


@app.route("/request_therapist", methods=['POST'])
def request_therapist():
    guest_id = request.form['guest_id']
    if therapists_available:
        chosen_therapist = random.choice(therapists_available)
        therapists_available.remove(chosen_therapist)
        connected_therapist[guest_id] = chosen_therapist.username
        connected_guest[chosen_therapist.username] = guest_id
        return chosen_therapist.username
    return None


@login_required
@app.route("/therapy_complete", methods=['POST'])
def therapy_complete():
    connected_therapist.pop(connected_guest[current_user.username])
    connected_guest.pop(current_user.username)
    therapists_available.append(current_user)


@app.route("/therapist_signout", methods=["POST"])
@login_required
def therapist_signout():
    user = load_user(request.form['username'])
    logout_user(user)
    therapists_available.remove(user)


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


@app.route("/generate_guest_id")
def generate_guest_id():
    return os.urandom(4)


@app.route("/message_from_therapist", methods=['POST'])
@login_required
def message_from_therapist():
    message = request.form['message']
    guest_id = connected_guest[current_user.username]
    pending_messages[guest_id] = (pending_messages.get(guest_id, "")
                                  + message + "\n")


@app.route("/message_from_user", methods=['POST'])
def message_from_user():
    message = request.form['message']
    guest_id = request.form['guest_id']
    therapist_username = connected_therapist[guest_id]
    pending_messages[therapist_username] = pending_messages.get(
        therapist_username, "") + message + "\n"


@app.route("/collect_guest_messages")
def collect_guest_messages():
    guest_id = request.form['guest_id']
    return pending_messages.pop(guest_id, "")


@app.route("/collect_therapist_messages")
@login_required
def collect_therapist_messages():
    therapist_username = current_user.username
    return pending_messages.pop(therapist_username, "")
