"""Entry point for the Aeneas Word Alignment Tool desktop application."""

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main() -> int:
    """Configure and run the Qt application. Returns the process exit code."""
    QCoreApplication.setOrganizationName("PrayerTools")
    QCoreApplication.setApplicationName("AeneasWordAlignmentTool")

    application = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
