"""Background worker that aligns a whole book's chapters in one run.

For each chapter it reads the chapter's text file and finds the matching
chapter's audio file (see ``app.bible_batch.discover_chapters``), runs the
same alignment pipeline the single-file tool uses (with prayer_type
"bible"), and saves the result beside the audio file.
"""

import tempfile
import time
from pathlib import Path
from typing import List

from PySide6.QtCore import QThread, Signal

from app.alignment_pipeline import AlignmentPipeline
from app.bible_batch import ChapterJob, discover_chapters
from app.errors import AlignmentError
from app.json_converter import JsonConverter
from app.logger import get_logger

logger = get_logger()

OUTPUT_SUFFIX = ".jsonl"


class BibleBatchWorker(QThread):
    """Runs the alignment pipeline for every chapter of a book.

    A failure on one chapter is logged and skipped rather than aborting the
    whole run, since a single bad recording shouldn't block the rest of the
    book.
    """

    chapter_progress = Signal(int, int)  # (completed_chapters, total_chapters)
    finished_success = Signal(int, list, float)  # (succeeded, failures, elapsed)
    failed = Signal(str)  # only for setup-level errors (bad folders, etc.)

    def __init__(
        self,
        text_folder: Path,
        audio_folder: Path,
        language_code: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.text_folder = text_folder
        self.audio_folder = audio_folder
        self.language_code = language_code
        self._pipeline = AlignmentPipeline()

    def run(self) -> None:
        """QThread entry point. Never raises — reports via signals instead."""
        overall_start = time.perf_counter()

        try:
            jobs, problems = discover_chapters(self.text_folder, self.audio_folder)
        except OSError as exc:
            self.failed.emit(f"Could not read the given folders: {exc}")
            return

        for problem in problems:
            logger.warning(problem)

        if not jobs:
            self.failed.emit(
                "No chapter text/audio pairs were found. Check the folder "
                "layout and chapter numbering."
            )
            return

        succeeded = 0
        failures: List[str] = []

        for index, job in enumerate(jobs):
            label = f"Chapter {job.chapter_number}"
            try:
                self._run_chapter(job, label)
                succeeded += 1
            except AlignmentError as exc:
                logger.error(f"{label} failed: {exc}")
                failures.append(f"{label}: {exc}")
            except Exception as exc:  # noqa: BLE001 - keep the batch going
                logger.exception(f"{label}: unexpected error")
                failures.append(f"{label}: unexpected error: {exc}")

            self.chapter_progress.emit(index + 1, len(jobs))

        overall_elapsed = time.perf_counter() - overall_start
        logger.info("Finished.")
        logger.info(f"Total execution time:\n{overall_elapsed:.2f} sec")
        self.finished_success.emit(succeeded, failures, overall_elapsed)

    def _run_chapter(self, job: ChapterJob, label: str) -> None:
        logger.info(f"{label}: starting ({job.text_path.name} + {job.audio_path.name})")
        if job.ambiguous_audio:
            logger.warning(
                f"{label}: multiple .wav files found, using {job.audio_path.name}."
            )

        transcript = job.text_path.read_text(encoding="utf-8")

        def run_stage(message, action):
            logger.info(f"{label}: {message}")
            return action()

        with tempfile.TemporaryDirectory(prefix="aeneas_bible_") as temp_dir_name:
            alignment = self._pipeline.run(
                job.audio_path,
                transcript,
                self.language_code,
                "bible",
                Path(temp_dir_name),
                run_stage,
            )

        output_path = job.audio_path.with_suffix(OUTPUT_SUFFIX)
        JsonConverter.save(alignment, output_path)
        logger.info(f"{label}: saved to {output_path}")
