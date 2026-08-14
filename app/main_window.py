"""Main window for the Aeneas Word Alignment Tool desktop application."""

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeySequence, QShortcut
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

from app.alignment_worker import AlignmentWorker
from app.constants import LANGUAGE_MAP
from app.logger import QtLogHandler, configure_logging

TYPE_MAP = {
    "Common": "common",
    "Rosary": "rosary",
    "Bible": "bible",
}

SETTINGS_AUDIO_DIR = "paths/audio_dir"
SETTINGS_OUTPUT_DIR = "paths/output_dir"
SETTINGS_LANGUAGE = "options/language"
SETTINGS_TYPE = "options/type"

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


class MainWindow(QMainWindow):
    """Top-level window: builds the UI and orchestrates the worker thread."""

    def __init__(self) -> None:
        super().__init__()

        self.settings = QSettings()
        self.audio_path: Optional[Path] = None
        self.worker: Optional[AlignmentWorker] = None

        self.setWindowTitle("Aeneas Word Alignment Tool")
        self.resize(1000, 820)
        self.setAcceptDrops(True)

        self._build_ui()
        self._configure_logging()
        self._restore_settings()

        self.generate_button.clicked.connect(self.on_generate_clicked)
        self.audio_browse_button.clicked.connect(self.on_browse_audio_clicked)
        self.output_browse_button.clicked.connect(self.on_browse_output_clicked)
        self.language_combo.currentIndexChanged.connect(self.on_language_changed)
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)

        save_shortcut = QShortcut(QKeySequence.StandardKey.Save, self)
        save_shortcut.activated.connect(self.on_generate_clicked)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(16)

        title_label = QLabel("Aeneas Word Alignment Tool")
        title_font = title_label.font()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title_label.setFont(title_font)
        root_layout.addWidget(title_label)

        root_layout.addWidget(self._build_audio_group())
        root_layout.addWidget(self._build_language_group())
        root_layout.addWidget(self._build_type_group())
        root_layout.addWidget(self._build_transcript_group())
        root_layout.addWidget(self._build_output_group())

        self.generate_button = QPushButton("Generate Alignment")
        self.generate_button.setStyleSheet(GREEN_BUTTON_STYLE)
        self.generate_button.setMinimumHeight(48)
        root_layout.addWidget(self.generate_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, AlignmentWorker.TOTAL_STAGES)
        self.progress_bar.setValue(0)
        root_layout.addWidget(self.progress_bar)

        root_layout.addWidget(self._build_log_group())

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready.")

    def _build_audio_group(self) -> QGroupBox:
        group = QGroupBox("Audio File")
        layout = QHBoxLayout(group)

        self.audio_browse_button = QPushButton("Browse...")
        self.audio_label = QLabel("No file selected")
        self.audio_label.setStyleSheet("color: #555;")

        layout.addWidget(self.audio_browse_button)
        layout.addWidget(self.audio_label, stretch=1)
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

    def _build_type_group(self) -> QGroupBox:
        group = QGroupBox("Type")
        layout = QHBoxLayout(group)

        self.type_combo = QComboBox()
        for display_name, code in TYPE_MAP.items():
            self.type_combo.addItem(display_name, userData=code)

        layout.addWidget(self.type_combo)
        layout.addStretch(1)
        return group

    def _build_transcript_group(self) -> QGroupBox:
        group = QGroupBox("Transcript")
        layout = QVBoxLayout(group)

        self.transcript_edit = QTextEdit()
        self.transcript_edit.setPlaceholderText(
            "Paste your prayer or transcript here...\n\n"
            "Leave a blank line between parts.\n"
            "For rosary type, mark bead boundaries with \\bead:1\\, \\bead:2\\, etc."
        )
        self.transcript_edit.setMinimumHeight(220)
        layout.addWidget(self.transcript_edit)
        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("Output File")
        layout = QHBoxLayout(group)

        self.output_edit = QLineEdit("alignment.json")
        self.output_browse_button = QPushButton("Browse...")

        layout.addWidget(self.output_edit, stretch=1)
        layout.addWidget(self.output_browse_button)
        return group

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("Progress")
        layout = QVBoxLayout(group)

        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(160)
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
        last_language = self.settings.value(SETTINGS_LANGUAGE, "English")
        index = self.language_combo.findText(last_language)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)

        last_type = self.settings.value(SETTINGS_TYPE, "Common")
        type_index = self.type_combo.findText(last_type)
        if type_index >= 0:
            self.type_combo.setCurrentIndex(type_index)

    def _audio_start_dir(self) -> str:
        return self.settings.value(SETTINGS_AUDIO_DIR, str(Path.home()))

    def _output_start_dir(self) -> str:
        return self.settings.value(SETTINGS_OUTPUT_DIR, str(Path.home()))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def on_browse_audio_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            self._audio_start_dir(),
            "WAV Files (*.wav)",
        )
        if file_path:
            self._set_audio_path(Path(file_path))

    def on_browse_output_clicked(self) -> None:
        default_name = self.output_edit.text().strip() or "alignment.json"
        start_path = str(Path(self._output_start_dir()) / default_name)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Output File",
            start_path,
            "JSON Files (*.json)",
        )
        if file_path:
            self.output_edit.setText(file_path)
            self.settings.setValue(SETTINGS_OUTPUT_DIR, str(Path(file_path).parent))

    def on_language_changed(self, _index: int) -> None:
        self.settings.setValue(SETTINGS_LANGUAGE, self.language_combo.currentText())

    def on_type_changed(self, _index: int) -> None:
        self.settings.setValue(SETTINGS_TYPE, self.type_combo.currentText())

    def on_generate_clicked(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return  # Already processing; ignore duplicate triggers (e.g. Ctrl+S).

        validation_error = self._validate_inputs()
        if validation_error:
            QMessageBox.warning(self, "Missing Information", validation_error)
            return

        transcript = self.transcript_edit.toPlainText()
        language_code = self.language_combo.currentData()
        prayer_type = self.type_combo.currentData()
        output_path = Path(self.output_edit.text().strip())

        self.log_edit.clear()
        self._set_controls_enabled(False)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Running alignment...")

        self.worker = AlignmentWorker(
            audio_path=self.audio_path,
            transcript=transcript,
            language_code=language_code,
            output_path=output_path,
            prayer_type=prayer_type,
        )
        self.worker.stage_progress.connect(self.on_stage_progress)
        self.worker.finished_success.connect(self.on_alignment_success)
        self.worker.failed.connect(self.on_alignment_failed)
        self.worker.start()

    def on_stage_progress(self, completed: int, total: int) -> None:
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(completed)

    def on_alignment_success(self, alignment: dict, elapsed_seconds: float) -> None:
        self._set_controls_enabled(True)
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.status_bar.showMessage(
            f"Finished in {elapsed_seconds:.2f} sec — saved to "
            f"{self.output_edit.text().strip()}"
        )

    def on_alignment_failed(self, message: str) -> None:
        self._set_controls_enabled(True)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage("Alignment failed.")
        QMessageBox.critical(self, "Alignment Failed", message)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate_inputs(self) -> Optional[str]:
        if self.audio_path is None:
            return "Please select a WAV audio file first."
        if not self.transcript_edit.toPlainText().strip():
            return "Please enter a transcript."
        if not self.output_edit.text().strip():
            return "Please choose an output filename."
        return None

    def _set_audio_path(self, path: Path) -> None:
        self.audio_path = path
        self.audio_label.setText(path.name)
        self.audio_label.setStyleSheet("color: #000;")
        self.settings.setValue(SETTINGS_AUDIO_DIR, str(path.parent))

    def _controls(self) -> List[QWidget]:
        return [
            self.audio_browse_button,
            self.language_combo,
            self.type_combo,
            self.transcript_edit,
            self.output_edit,
            self.output_browse_button,
            self.generate_button,
        ]

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in self._controls():
            widget.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Drag and drop support
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and self._first_wav_url(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        wav_path = self._first_wav_url(event)
        if wav_path is not None:
            self._set_audio_path(wav_path)
            event.acceptProposedAction()
        else:
            event.ignore()

    @staticmethod
    def _first_wav_url(event) -> Optional[Path]:
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if local_path.lower().endswith(".wav"):
                return Path(local_path)
        return None

    # ------------------------------------------------------------------
    # Window lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.warning(
                self,
                "Alignment in Progress",
                "Please wait for the current alignment to finish before closing.",
            )
            event.ignore()
            return
        event.accept()
