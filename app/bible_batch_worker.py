"""Background worker that aligns a whole book's chapters in one run.

Chapters are aligned in parallel across a pool of worker *processes* (not
threads - see ``app.bible_chapter_task`` for why). For each chapter, the
worker process reads the chapter's text file, finds the matching chapter's
audio file (see ``app.bible_batch.discover_jobs``), runs the same alignment
pipeline the single-file tool uses (with prayer_type "bible"), and saves the
result beside the audio file.
"""

import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path
from typing import List

from PySide6.QtCore import QThread, Signal

from app.bible_batch import discover_jobs
from app.bible_chapter_task import OUTPUT_SUFFIX, process_chapter
from app.logger import get_logger

logger = get_logger()

DEFAULT_MAX_WORKERS = 4


class BibleBatchWorker(QThread):
    """Runs the alignment pipeline for every chapter of a book, in parallel.

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
        max_workers: int = DEFAULT_MAX_WORKERS,
        skip_existing: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.text_folder = text_folder
        self.audio_folder = audio_folder
        self.language_code = language_code
        self.max_workers = max_workers
        self.skip_existing = skip_existing

    def run(self) -> None:
        """QThread entry point. Never raises — reports via signals instead."""
        overall_start = time.perf_counter()

        try:
            jobs, problems = discover_jobs(self.text_folder, self.audio_folder)
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
        completed = 0
        total = len(jobs)

        if self.skip_existing:
            to_run = []
            for job in jobs:
                output_path = job.audio_path.with_suffix(OUTPUT_SUFFIX)
                if output_path.exists():
                    label = (
                        f"{job.book_name} Chapter {job.chapter_number}"
                        if job.book_name
                        else f"Chapter {job.chapter_number}"
                    )
                    logger.info(f"{label}: already aligned, skipping ({output_path}).")
                    succeeded += 1
                    completed += 1
                    self.chapter_progress.emit(completed, total)
                else:
                    to_run.append(job)
            jobs = to_run

        if not jobs:
            overall_elapsed = time.perf_counter() - overall_start
            logger.info("Finished.")
            logger.info(f"Total execution time:\n{overall_elapsed:.2f} sec")
            self.finished_success.emit(succeeded, failures, overall_elapsed)
            return

        worker_count = max(1, min(self.max_workers, len(jobs)))
        logger.info(f"Aligning {len(jobs)} chapter(s) with {worker_count} in parallel.")

        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            pending = {
                executor.submit(
                    process_chapter,
                    job.book_name,
                    job.chapter_number,
                    job.text_path,
                    job.audio_path,
                    self.language_code,
                    job.ambiguous_audio,
                )
                for job in jobs
            }

            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    completed += 1
                    try:
                        result = future.result()
                    except Exception as exc:  # noqa: BLE001 - a worker process crashed
                        logger.exception("A chapter's worker process crashed")
                        failures.append(f"unexpected error: {exc}")
                        self.chapter_progress.emit(completed, total)
                        continue

                    for line in result.log_lines:
                        logger.info(line)

                    if result.success:
                        succeeded += 1
                    else:
                        failures.append(f"{result.label}: {result.error}")

                    self.chapter_progress.emit(completed, total)

        overall_elapsed = time.perf_counter() - overall_start
        logger.info("Finished.")
        logger.info(f"Total execution time:\n{overall_elapsed:.2f} sec")
        self.finished_success.emit(succeeded, failures, overall_elapsed)
