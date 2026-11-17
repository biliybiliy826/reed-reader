"""Background IO only; every completion is delivered through Qt signals."""

import traceback
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    finished = Signal()


class Task(QRunnable):
    def __init__(self, fn: Callable):
        super().__init__()
        self.fn = fn
        self.signals = Signals()

    @Slot()
    def run(self):
        try:
            result = self.fn()
        except Exception as exc:
            traceback.print_exc()
            self.signals.failed.emit(str(exc))
        else:
            self.signals.done.emit(result)
        finally:
            self.signals.finished.emit()


class Jobs(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(3)
        self.tasks = set()

    def run(self, fn, done, failed):
        task = Task(fn)
        self.tasks.add(task)
        task.signals.done.connect(done)
        task.signals.failed.connect(failed)
        task.signals.finished.connect(lambda: self.tasks.discard(task))
        self.pool.start(task)
