"""Logging setup that bridges Python's ``logging`` module to the Qt GUI.

Worker code (running on a background ``QThread``) logs through the
standard ``logging`` module. A ``QtLogHandler`` converts each log record
into a Qt signal so the main window can safely append it to the on-screen
log widget, regardless of which thread produced the record.
"""

import logging

from PySide6.QtCore import QObject, Signal

LOGGER_NAME = "aeneas_word_alignment_tool"


class QtLogHandler(QObject, logging.Handler):
    """A ``logging.Handler`` that re-emits records as a Qt signal.

    Qt signal/slot connections between different threads are queued
    automatically, so this is a thread-safe way to stream log messages
    from a background worker into a GUI widget on the main thread.
    """

    log_emitted = Signal(str)

    def __init__(self) -> None:
        QObject.__init__(self)
        logging.Handler.__init__(self)
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        message = self.format(record)
        self.log_emitted.emit(message)


def configure_logging(qt_handler: QtLogHandler) -> logging.Logger:
    """Attach ``qt_handler`` (and a console handler) to the app logger."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    logger.addHandler(qt_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(console_handler)

    return logger


def get_logger() -> logging.Logger:
    """Return the application's shared logger instance."""
    return logging.getLogger(LOGGER_NAME)
