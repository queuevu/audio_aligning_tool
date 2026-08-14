"""Background worker that runs the full alignment pipeline off the GUI thread."""

import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, TypeVar

from PySide6.QtCore import QThread, Signal

from app.alignment_pipeline import AlignmentPipeline
from app.errors import AlignmentError
from app.json_converter import JsonConverter
from app.logger import get_logger

logger = get_logger()

_T = TypeVar("_T")


class AlignmentWorker(QThread):
    """Runs the alignment pipeline on a background thread for the GUI.

    All heavy lifting happens in ``run()``, which executes on a separate
    thread so the GUI event loop is never blocked. Progress and results
    are reported back to the GUI thread via Qt signals only.
    """

    # 5 pipeline stages (see AlignmentPipeline.run) plus this worker's own
    # "Saving JSON..." stage.
    TOTAL_STAGES = 6

    stage_progress = Signal(int, int)  # (completed_stage_count, total_stages)
    finished_success = Signal(dict, float)  # (alignment_json, total_elapsed_seconds)
    failed = Signal(str)  # user-friendly error message

    def __init__(
        self,
        audio_path: Path,
        transcript: str,
        language_code: str,
        output_path: Path,
        prayer_type: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.audio_path = audio_path
        self.transcript = transcript
        self.language_code = language_code
        self.output_path = output_path
        self.prayer_type = prayer_type
        self._pipeline = AlignmentPipeline()
        self._completed_stages = 0

    def run(self) -> None:
        """QThread entry point. Never raises — reports via signals instead."""
        overall_start = time.perf_counter()
        self._completed_stages = 0

        try:
            with tempfile.TemporaryDirectory(prefix="aeneas_") as temp_dir_name:
                temp_dir = Path(temp_dir_name)

                alignment = self._pipeline.run(
                    self.audio_path,
                    self.transcript,
                    self.language_code,
                    self.prayer_type,
                    temp_dir,
                    self._run_stage,
                )

                self._run_stage(
                    "Saving JSON...",
                    lambda: JsonConverter.save(alignment, self.output_path),
                )

            overall_elapsed = time.perf_counter() - overall_start
            logger.info("Finished.")
            logger.info(f"Total execution time:\n{overall_elapsed:.2f} sec")
            self.finished_success.emit(alignment, overall_elapsed)

        except AlignmentError as exc:
            logger.error(str(exc))
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001 - never leak a raw traceback
            logger.exception("Unexpected error during alignment")
            self.failed.emit(f"An unexpected error occurred: {exc}")

    def _run_stage(self, message: str, action: Callable[[], _T]) -> _T:
        """Log a stage's start/finish, time it, and report progress."""
        logger.info(message)
        stage_start = time.perf_counter()

        result = action()

        stage_elapsed = time.perf_counter() - stage_start
        logger.info(f"Done ({stage_elapsed:.2f} sec)")

        self._completed_stages += 1
        self.stage_progress.emit(self._completed_stages, self.TOTAL_STAGES)

        return result
