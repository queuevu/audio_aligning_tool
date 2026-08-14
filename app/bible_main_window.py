"""Main window for the Bible Batch Alignment Tool desktop application."""

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.bible_batch_worker import BibleBatchWorker
from app.constants import LANGUAGE_MAP
from app.logger import QtLogHandler, configure_logging

SETTINGS_TEXT_DIR = "paths/text_dir"
SETTINGS_AUDIO_DIR = "paths/audio_dir"
SETTINGS_LANGUAGE = "options/language"

GREEN_BUTTON_STYLE = """
QPushButton {
    background-color: #2ecc71;
    color: white;
    font-size: 15px;
    font-weight: 600;
    padding: 12px;
    border-radius: 8px;
    border: none;
}
QPushButton:hover {
    background-color: #27ae60;
}
QPushButton:disabled {
    background-color: #a5d6b7;
    color: #f0f0f0;
}
"""


class BibleMainWindow(QMainWindow):
    """Top-level window: builds the UI and orchestrates the batch worker thread."""

    def __init__(self) -> None:
        super().__init__()

        self.settings = QSettings()
        self.worker: Optional[BibleBatchWorker] = None

        self.setWindowTitle("Bible Batch Alignment Tool")
        self.resize(1000, 780)

        self._build_ui()
        self._configure_logging()
        self._restore_settings()

        self.generate_button.clicked.connect(self.on_generate_clicked)
        self.text_browse_button.clicked.connect(self.on_browse_text_clicked)
        self.audio_browse_button.clicked.connect(self.on_browse_audio_clicked)
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(16)

        title_label = QLabel("Bible Batch Alignment Tool")
        title_font = title_label.font()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        root_layout.addWidget(title_label)

        description_label = QLabel(
            "Point this at a book's chapter-text folder and chapter-audio "
            "folder; every chapter is aligned and its JSON is saved beside "
            "its audio file."
        )
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: #555;")
        root_layout.addWidget(description_label)

        root_layout.addWidget(self._build_text_folder_group())
        root_layout.addWidget(self._build_audio_folder_group())
        root_layout.addWidget(self._build_language_group())

        self.generate_button = QPushButton("Generate All Chapters")
        self.generate_button.setStyleSheet(GREEN_BUTTON_STYLE)
        self.generate_button.setMinimumHeight(48)
        root_layout.addWidget(self.generate_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        root_layout.addWidget(self.progress_bar)

        root_layout.addWidget(self._build_log_group())

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

    def _build_text_folder_group(self) -> QGroupBox:
        group = QGroupBox("Chapter Text Folder (book_name/Chapter1.txt, ...)")
        layout = QHBoxLayout(group)

        self.text_folder_edit = QLineEdit()
        self.text_browse_button = QPushButton("Browse...")

        layout.addWidget(self.text_folder_edit, stretch=1)
        layout.addWidget(self.text_browse_button)
        return group

    def _build_audio_folder_group(self) -> QGroupBox:
        group = QGroupBox("Chapter Audio Folder (book_name/Chapter1/*.wav, ...)")
        layout = QHBoxLayout(group)

        self.audio_folder_edit = QLineEdit()
        self.audio_browse_button = QPushButton("Browse...")

        layout.addWidget(self.audio_folder_edit, stretch=1)
        layout.addWidget(self.audio_browse_button)
        return group

    def _build_language_group(self) -> QGroupBox:
        group = QGroupBox("Language")
        layout = QHBoxLayout(group)

        self.language_combo = QComboBox()
        for display_name, code in LANGUAGE_MAP.items():
            self.language_combo.addItem(display_name, userData=code)

        layout.addWidget(self.language_combo)
        layout.addStretch(1)
        return group

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("Progress")
        layout = QVBoxLayout(group)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(280)
        self.log_edit.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; font-family: monospace;"
        )
        layout.addWidget(self.log_edit)
        return group

    def _configure_logging(self) -> None:
        self._log_handler = QtLogHandler()
        self._log_handler.log_emitted.connect(self.log_edit.append)
        configure_logging(self._log_handler)

    # ------------------------------------------------------------------
    # Settings persistence
    # ------------------------------------------------------------------

    def _restore_settings(self) -> None:
        self.text_folder_edit.setText(self.settings.value(SETTINGS_TEXT_DIR, ""))
        self.audio_folder_edit.setText(self.settings.value(SETTINGS_AUDIO_DIR, ""))

        last_language = self.settings.value(SETTINGS_LANGUAGE, "English")
        index = self.language_combo.findText(last_language)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def on_browse_text_clicked(self) -> None:
        start_dir = self.text_folder_edit.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self, "Select Chapter Text Folder", start_dir
        )
        if folder:
            self.text_folder_edit.setText(folder)
            self.settings.setValue(SETTINGS_TEXT_DIR, folder)

    def on_browse_audio_clicked(self) -> None:
        start_dir = self.audio_folder_edit.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self, "Select Chapter Audio Folder", start_dir
        )
        if folder:
            self.audio_folder_edit.setText(folder)
            self.settings.setValue(SETTINGS_AUDIO_DIR, folder)

    def on_language_changed(self, _index: int) -> None:
        self.settings.setValue(SETTINGS_LANGUAGE, self.language_combo.currentText())

    def on_generate_clicked(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return  # Already processing; ignore duplicate triggers.

        validation_error = self._validate_inputs()
        if validation_error:
            QMessageBox.warning(self, "Missing Information", validation_error)
            return

        language_code = self.language_combo.currentData()

        self.log_edit.clear()
        self._set_controls_enabled(False)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Running batch alignment...")

        self.worker = BibleBatchWorker(
            text_folder=Path(self.text_folder_edit.text().strip()),
            audio_folder=Path(self.audio_folder_edit.text().strip()),
            language_code=language_code,
        )
        self.worker.chapter_progress.connect(self.on_chapter_progress)
        self.worker.finished_success.connect(self.on_batch_success)
        self.worker.failed.connect(self.on_batch_failed)
        self.worker.start()

    def on_chapter_progress(self, completed: int, total: int) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(completed)

    def on_batch_success(
        self, succeeded: int, failures: List[str], elapsed_seconds: float
    ) -> None:
        self._set_controls_enabled(True)

        if failures:
            self.status_bar.showMessage(
                f"Finished in {elapsed_seconds:.2f} sec — "
                f"{succeeded} chapter(s) succeeded, {len(failures)} failed."
            )
            QMessageBox.warning(
                self,
                "Some Chapters Failed",
                f"{succeeded} chapter(s) succeeded.\n\n"
                "Failed:\n" + "\n".join(failures),
            )
        else:
            self.status_bar.showMessage(
                f"Finished in {elapsed_seconds:.2f} sec — "
                f"all {succeeded} chapter(s) succeeded."
            )

    def on_batch_failed(self, message: str) -> None:
        self._set_controls_enabled(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Batch alignment failed.")
        QMessageBox.critical(self, "Batch Alignment Failed", message)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_inputs(self) -> Optional[str]:
        text_folder = self.text_folder_edit.text().strip()
        audio_folder = self.audio_folder_edit.text().strip()

        if not text_folder or not Path(text_folder).is_dir():
            return "Please choose a valid chapter text folder."
        if not audio_folder or not Path(audio_folder).is_dir():
            return "Please choose a valid chapter audio folder."
        return None

    def _controls(self) -> List[QWidget]:
        return [
            self.text_folder_edit,
            self.text_browse_button,
            self.audio_folder_edit,
            self.audio_browse_button,
            self.language_combo,
            self.generate_button,
        ]

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in self._controls():
            widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.warning(
                self,
                "Batch Alignment in Progress",
                "Please wait for the current batch to finish before closing.",
            )
            event.ignore()
            return
        event.accept()
