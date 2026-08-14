"""Entry point for the Bible Batch Alignment Tool desktop application."""

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from app.bible_main_window import BibleMainWindow


def main() -> int:
    """Configure and run the Qt application. Returns the process exit code."""
    QCoreApplication.setOrganizationName("PrayerTools")
    QCoreApplication.setApplicationName("BibleBatchAlignmentTool")

    application = QApplication(sys.argv)
    window = BibleMainWindow()
    window.show()

    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
