"""Bridge between Python's logging module and Qt's signal system.

QtLogHandler intercepts all log records emitted by the bot (running in
the worker thread) and forwards them to the GUI (main thread) via
thread-safe Qt signals with automatic QueuedConnection.
"""

import logging
from PyQt6.QtCore import QObject, pyqtSignal
from .thread_safety import LogRecord


class LogSignal(QObject):
    """QObject that emits a signal when a log record is received.

    This object lives in the main thread. The signal is connected to
    LogPage.append_log(). Because QtLogHandler.emit() runs in the worker
    thread, the signal uses auto QueuedConnection to safely deliver the
    record to the main thread's event loop.
    """
    record_received = pyqtSignal(LogRecord)


class QtLogHandler(logging.Handler):
    """A logging.Handler that forwards records to a LogSignal.

    Install on the root logger to capture all log output and display
    it in the GUI's log viewer. Thread-safe: emit() is called from
    whichever thread the logger is used in; the pyqtSignal handles
    cross-thread delivery.
    """

    def __init__(self, log_signal: LogSignal, level: int = logging.DEBUG):
        super().__init__(level)
        self._signal = log_signal
        # Use a simple formatter — the GUI will format for display
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

    def emit(self, record: logging.LogRecord) -> None:
        """Convert stdlib LogRecord to GUI LogRecord and emit via signal."""
        try:
            gui_record = LogRecord(
                timestamp=record.created,
                level=record.levelname,
                logger_name=record.name,
                message=self.format(record),
            )
            self._signal.record_received.emit(gui_record)
        except Exception:
            self.handleError(record)
