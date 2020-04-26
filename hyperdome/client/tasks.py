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

    def __str__(self):
        return f"QtTask({self.fn.__name__})"


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
        run_after_task._log.debug(f"{fn} set as result callback for {task}")
        if auto_run and isinstance(task, QtTask):
            run_after_task._log.debug(f"starting {task} on the global threadpool")
            QtCore.QThreadPool.globalInstance().start(task)
        elif auto_run and isinstance(task, QtIntervalTask):
            run_after_task._log.debug(f"starting {task} in its own thread")
            task.start()
        else:
            err_str = f"{task} is not an accepted task type"
            run_after_task._log.error(err_str)
            raise TypeError(err_str)
        return fn

    return register_and_run
