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
import functools
from hyperdome.client.hyperdome_client import HyperdomeClient
import json
import typing

from PyQt5 import QtCore
import autologging
import requests
from werkzeug.exceptions import MethodNotAllowed

from ..common.onion import (
    BundledTorTimeout,
    TorErrorAuthError,
    TorErrorAutomatic,
    TorErrorInvalidSetting,
    TorErrorMissingPassword,
    TorErrorProtocolError,
    TorErrorSocketFile,
    TorErrorSocketPort,
    TorErrorUnreadableCookieFile,
    TorTooOld,
)
from ..common.server import Server
import enum


class QtSignals(QtCore.QObject):
    """
    generic signals class for QTask callbacks

    result: called on success, any object

    error: called on a failure, an Exception object

    finished: called when task is completely finished
    """

    result = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(Exception)
    finished = QtCore.pyqtSignal()


@autologging.logged
class QtTask(QtCore.QRunnable):
    """
    generic task to execute any function on a threadpool

    fn: callable ran by the threadpool

    *args, **kwargs: arguments passed to the function
    """

    def __init__(self, fn: typing.Callable, *args, **kwargs):
        self.__log.log(autologging.TRACE, "CALL")
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = QtSignals()
        self.__log.debug("task created")

    @QtCore.pyqtSlot()
    def run(self):
        self.__log.log(autologging.TRACE, "CALL")
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
            self.__log.debug("task successful")
        except Exception as error:
            self.signals.error.emit(error)
            # calling thread should log error
            self.__log.debug("task failed")
        finally:
            self.signals.finished.emit()
            self.__log.log(autologging.TRACE, "RETURN")


@autologging.logged
class QtIntervalTask(QtCore.QThread):
    """
    Generic thread that runs a function on a seperate thread on some interval

    fn: the callable to be ran in set intervals

    interval: milliseconds to wait between calling fn

    *args, **kwargs: arguments passed to the function
    """

    def __init__(self, fn: typing.Callable, *args, interval: int = 1000, **kwargs):
        self.__log.log(autologging.TRACE, "CALL")
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.interval = interval
        self.signals = QtSignals()
        self._stopped = False
        self.__log.debug("interval task created")

    def run(self):
        self.__log.log(autologging.TRACE, "CALL")
        while not self.stopped:
            self.__log.log(autologging.TRACE, "running")
            try:
                result = self.fn(*self.args, **self.kwargs)
                self.signals.result.emit(result)
                self.__log.debug("interval loop successful")
            except Exception as error:
                self.signals.error.emit(error)
                # calling thread should log error
                self.__log.debug("interval loop failed")
            finally:
                self.wait(self.interval)
        else:
            self.__log.debug("interval task exited")
            self.signals.finished.emit()

    @QtCore.pyqtSlot()
    def stop(self):
        self.__log.debug("stop task requested")
        self._stopped = True

    @property
    def stopped(self):
        self.__log.log(autologging.TRACE, f"RETURN {self._stopped}")
        return self._stopped


@autologging.logged
class OnionThread(QtCore.QThread):
    """
    Starts the onion service, and waits for it to finish
    """

    success = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def __init__(self, mode):
        super(OnionThread, self).__init__()
        self.mode = mode
        self.__log.debug("__init__")

        # allow this thread to be terminated
        self.setTerminationEnabled()

    def run(self):

        self.mode.app.stay_open = not self.mode.common.settings.get(
            "close_after_first_download"
        )

        # wait for modules in thread to load, preventing a thread-related
        # cx_Freeze crash
        self.wait(200)

        try:
            self.mode.app.start_onion_service()
            self.success.emit()

        except (
            TorTooOld,
            TorErrorInvalidSetting,
            TorErrorAutomatic,
            TorErrorSocketPort,
            TorErrorSocketFile,
            TorErrorMissingPassword,
            TorErrorUnreadableCookieFile,
            TorErrorAuthError,
            TorErrorProtocolError,
            BundledTorTimeout,
            OSError,
        ) as e:
            self.error.emit(e.args[0])
            self.__log.exception("problem starting Tor")
            return


class TaskSignals(QtCore.QObject):
    success = QtCore.pyqtSignal(str)
    error = QtCore.pyqtSignal(str)


# TODO: implement logging in these classes post refactor


class SendMessageTask(QtCore.QRunnable):
    """
    send client message to server
    """

    signals = TaskSignals()

    def __init__(
        self, server: Server, session: requests.Session, uid: str, message: str
    ):
        super(SendMessageTask, self).__init__()
        self.server = server
        self.session = session
        self.uid = uid
        self.message = message

    @QtCore.pyqtSlot()
    def run(self):
        try:
            send_message(self.server, self.session, self.uid, self.message)
        except requests.RequestException:
            self.signals.error.emit("Couldn't send message")


class GetUidTask(QtCore.QRunnable):
    """
    Get a UID from the server
    """

    signals = TaskSignals()

    def __init__(self, server: Server, session: requests.Session):
        super(GetUidTask, self).__init__()
        self.server = server
        self.session = session

    @QtCore.pyqtSlot()
    def run(self):
        try:
            uid = get_uid(self.server, self.session)
            self.signals.success.emit(uid)
        except requests.RequestException:
            self.signals.error.emit("couldn't get UID")


class StartChatTask(QtCore.QRunnable):
    """
    Signin counselor, or request counselor session if user
    """

    signals = TaskSignals()

    def __init__(
        self,
        server: Server,
        session: requests.Session,
        uid: str,
        pub_key: str,
        signature: str = "",
    ):
        super(StartChatTask, self).__init__()
        self.server = server
        self.session = session
        self.uid = uid
        self.pub_key = pub_key
        self.signature = signature

    @QtCore.pyqtSlot()
    def run(self):
        try:
            self.signals.success.emit(
                start_chat(
                    self.server, self.session, self.uid, self.pub_key, self.signature
                )
            )
        except requests.RequestException:
            self.signals.error.emit("Couldn't start a chat session")


class GetMessagesTask(QtCore.QRunnable):
    """
    retrieve new messages on a fixed interval
    """

    signals = TaskSignals()

    def __init__(self, session: requests.Session, server: Server, uid: str):
        super(GetMessagesTask, self).__init__()
        self.session = session
        self.server = server
        self.uid = uid

    @QtCore.pyqtSlot()
    def run(self):
        try:
            message_response = get_messages(self.server, self.session, self.uid)
            if message_response["chat_status"] == "CHAT_ACTIVE":
                self.signals.success.emit(message_response["messages"])
            elif message_response["chat_status"] == "CHAT_OVER":
                self.signals.error.emit("chat ended")
        except requests.HTTPError:
            self.signals.error.emit("Counselor not in chat")
        except requests.RequestException:
            self.signals.error.emit("Error in get messages request")
        except MethodNotAllowed:
            self.signals.error.emit("not allowed")
        except KeyError:
            self.signals.error.emit("API error")


class EndChatTask(QtCore.QRunnable):
    """
    inform the server that the current chat session is concluded,
    freeing up the counselor for a new guest, and disconnecting the guest
    """

    signals = TaskSignals()

    def __init__(self, session: requests.Session, server: Server, uid: str):
        super(EndChatTask, self).__init__()
        self.session = session
        self.server = server
        self.uid = uid

    @QtCore.pyqtSlot()
    def run(self):
        try:
            self.session.post(
                f"{self.server.url}/counseling_complete", data={"user_id": self.uid}
            ).raise_for_status()
            self.signals.success.emit("good")
        except:
            self.signals.error.emit("you're stuck here now")


class CounselorSignoutTask(QtCore.QRunnable):
    """
    deregister counselor identified from active list,
    stopping them from receiving additional guests
    """

    signals = TaskSignals()

    def __init__(self, session: requests.Session, server: Server, uid: str):
        super(CounselorSignoutTask, self).__init__()
        self.session = session
        self.server = server
        self.uid = uid

    @QtCore.pyqtSlot()
    def run(self):
        try:
            self.session.post(
                f"{self.server.url}/counselor_signout", data={"user_id": self.uid}
            )
            self.signals.success.emit("good")
        except:
            self.signals.error.emit("you're stuck here now")


class PollForConnectedGuestTask(QtCore.QRunnable):
    """
    ask server if a guest has requested to connect yet
    and return the public key when they have
    """

    signals = TaskSignals()

    def __init__(self, session: requests.Session, server: Server, uid: str):
        super(PollForConnectedGuestTask, self).__init__()
        self.task = functools.partial(get_guest_pub_key, server, session, uid)

    @QtCore.pyqtSlot()
    def run(self):
        try:
            self.signals.success.emit(self.task())
        except:
            self.signals.error.emit("problem getting guest pubkey")


@autologging.traced
@autologging.logged
def send_message(server: Server, session: requests.Session, uid: str, message: str):
    """
    Send message to server provided using session for given user
    """
    session.post(
        f"{server.url}/send_message", data={"message": message, "user_id": uid}
    )


@autologging.traced
@autologging.logged
def get_uid(server: Server, session: requests.Session):
    """
    Ask server for a new UID for a new user session
    """
    response = session.get(f"{server.url}/generate_guest_id")
    try:
        response.raise_for_status()
    except requests.HTTPError:
        get_uid._log.exception(response.text)
        raise
    else:
        return response.text


@autologging.traced
def get_messages(server: Server, session: requests.Session, uid: str):
    """
    collect new messages waiting on server for active session
    """
    response = session.get(
        f"{server.url}/collect_messages", data={"user_id": uid}
    ).json()
    try:
        response.raise_for_status()
    except requests.HTTPError:
        pass


def handle_requests_errors(fn: typing.Callable):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            getattr(fn, "_log")
        except AttributeError:
            return fn(*args, **kwargs)
        try:
            response = fn(*args, **kwargs)
        except requests.ConnectionError:
            handle_requests_errors._log.warning("couldn't connect to server")
            raise
        except requests.Timeout:
            handle_requests_errors._log.warning("server timed out during request")
            raise
        except requests.HTTPError:
            raise
        else:
            return response

    return wrapper


@autologging.traced
@autologging.logged
@handle_requests_errors
def start_chat(
    server: Server,
    session: requests.Session,
    uid: str,
    pub_key: str,
    signature: str = "",
):
    if server.is_counselor:
        return session.post(
            f"{server.url}/counselor_signin",
            data={
                "pub_key": pub_key,
                "signature": signature,
                "username": server.username,
            },
        ).text

    else:
        return session.post(
            f"{server.url}/request_counselor",
            data={"guest_id": uid, "pub_key": pub_key},
        ).text


COMPATIBLE_SERVERS = ["0.2", "0.2.0", "0.2.1"]


@autologging.traced
@autologging.logged
@handle_requests_errors
def probe_server(server: Server, session: requests.Session):
    info = json.loads(session.get(f"{server.url}/probe").text)
    if info["name"] != "hyperdome":
        return "not hyperdome"
    if info["version"] not in COMPATIBLE_SERVERS:
        return "bad version"
    return ""


@autologging.traced
@autologging.logged
@handle_requests_errors
def get_guest_pub_key(server: Server, session: requests.Session, uid: str):
    return session.get(
        f"{server.url}/poll_connected_guest", data={"counselor_id": uid}
    ).text


@autologging.traced
@autologging.logged
@handle_requests_errors
def signup_counselor(
    server: Server,
    session: requests.Session,
    passcode: str,
    pub_key: str,
    signature: str,
):
    return session.post(
        f"{server.url}/counselor_signup",
        data={
            "username": server.username,
            "pub_key": pub_key,
            "signup_code": passcode,
            "signature": signature,
        },
    ).text
