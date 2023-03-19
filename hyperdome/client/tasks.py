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
import typing

from PyQt5 import QtCore
import autologging


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
from typing import Type, get_type_hints


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
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = QtSignals()
        self.__log.debug(f"task {self} created")

    @QtCore.pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
            self.__log.debug(f"task {self} successful")
        except Exception as error:
            self.signals.error.emit(error)
            # calling thread should log error
            self.__log.debug(f"task {self} failed")
        finally:
            self.signals.finished.emit()

    def __str__(self):
        return f"QtTask({self.fn.__name__})"


@autologging.logged
class QtIntervalTask(QtCore.QThread):
    """
    Generic thread that runs a function on a seperate thread on some interval

    fn: the callable to be ran in set intervals

    interval: integer seconds to wait between runs

    *args, **kwargs: arguments passed to the function
    """

    def __init__(
        self,
        fn: typing.Callable,
        *args,
        parent: QtCore.QObject = None,
        interval: int = 1000,
        **kwargs,
    ):
        super().__init__(parent)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = QtSignals()
        self.interval = interval
        self.__log.debug(f"interval task {self} created")

    def run(self):
        self.__log.debug(f"interval task {self} started")

        @QtCore.pyqtSlot()
        def process():
            try:
                result = self.fn(*self.args, **self.kwargs)
                self.signals.result.emit(result)
                self.__log.debug(f"interval task {self} successful")
            except Exception as error:
                self.signals.error.emit(error)
                # calling thread should log error
                self.__log.debug(f"interval task {self} failed")

        timer = QtCore.QTimer()
        timer.setInterval(self.interval)
        timer.timeout.connect(process)
        timer.start()
        self.exec_()
        self.__log.debug(f"interval task {self} finished")

    @QtCore.pyqtSlot()
    def stop(self):
        self.__log.debug(f"stop requested for {self}")
        self.quit()

    def __str__(self):
        return f"QtIntervalTask({self.fn.__name__})"


@autologging.logged
class OnionThread(QtCore.QThread):
    """
    Starts the onion service, and waits for it to finish
    """

    success = QtCore.pyqtSignal()
    error = QtCore.pyqtSignal(str)

    def __init__(self, mode):
        super().__init__()
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


@autologging.logged
def run_after_task(
    task: typing.Union[QtTask, QtIntervalTask],
    error_handler: QtCore.pyqtSlot = None,
    finished_handler: QtCore.pyqtSlot = None,
    auto_run=True,
):
    """
    connects signals to provided handlers
    and returns a function that will register the input function
    as the result signal handler and optionally begin running the task
    on the global threadpool instance.

    Can be used as a decorator.
    """
    if error_handler is not None:
        task.signals.error.connect(error_handler)
        run_after_task._log.debug(
            f"{error_handler.__name__} set as failure callback for {task}"
        )
    if finished_handler is not None:
        task.signals.finished.connect(finished_handler)
        run_after_task._log.debug(
            f"{finished_handler} set as finished callback for {task}"
        )

    def register_and_run(fn: QtCore.pyqtSlot):
        task.signals.result.connect(fn)
        run_after_task._log.debug(f"{fn.__name__} set as result callback for {task}")
        if auto_run:
            if isinstance(task, QtTask):
                run_after_task._log.debug(f"starting {task} on the global threadpool")
                QtCore.QThreadPool.globalInstance().start(task)
            elif isinstance(task, QtIntervalTask):
                run_after_task._log.debug(f"starting {task} in its own thread")
                task.start()
            else:
                err_str = (
                    f"{type(task)} is not an accepted task type: "
                    f"{get_type_hints(register_and_run)}"
                )
                run_after_task._log.error(err_str)
                raise TypeError(err_str)
        return fn

    return register_and_run
