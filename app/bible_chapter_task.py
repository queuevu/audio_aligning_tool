"""Runs a single chapter's alignment. Designed to run in a worker process.

This has to be a plain, top-level function (not a method) so it can be sent
to a ``ProcessPoolExecutor`` worker: multiprocessing pickles the function by
its import path, and its arguments must be picklable too (``Path``/``str``/
``int``/``bool``, which they are here).

Aeneas isn't safe to call from multiple threads in one process - its runner
temporarily swaps ``sys.stdout``/``sys.stderr`` globally for the duration of
each call (see ``AeneasRunner.run``), which would race across threads.
Separate processes each get their own global state, so real OS processes -
not threads - are what let chapters align in parallel.
"""

import logging
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from app.alignment_pipeline import AlignmentPipeline
from app.errors import AlignmentError
from app.json_converter import JsonConverter
from app.logger import LOGGER_NAME

OUTPUT_SUFFIX = ".jsonl"


@dataclass
class ChapterResult:
    """What one ``process_chapter`` call reports back to the parent process."""

    book_name: str
    chapter_number: int
    label: str
    success: bool
    output_path: str = ""
    error: str = ""
    log_lines: List[str] = field(default_factory=list)


class _ListHandler(logging.Handler):
    """Collects formatted log records into a plain list.

    Used instead of the GUI's ``QtLogHandler`` because this runs in a
    separate process with no Qt event loop - the collected lines are handed
    back to the parent process for it to log/display normally.
    """

    def __init__(self, sink: List[str]) -> None:
        super().__init__()
        self._sink = sink
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        self._sink.append(self.format(record))


def process_chapter(
    book_name: str,
    chapter_number: int,
    text_path: Path,
    audio_path: Path,
    language_code: str,
    ambiguous_audio: bool,
) -> ChapterResult:
    """Align one chapter end-to-end and save its JSON beside the audio file."""
    label = (
        f"{book_name} Chapter {chapter_number}"
        if book_name
        else f"Chapter {chapter_number}"
    )

    log_lines: List[str] = []
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    handler = _ListHandler(log_lines)
    logger.addHandler(handler)

    try:
        logger.info(f"{label}: starting ({text_path.name} + {audio_path.name})")
        if ambiguous_audio:
            logger.warning(
                f"{label}: multiple .wav files found, using {audio_path.name}."
            )

        transcript = text_path.read_text(encoding="utf-8")

        def run_stage(message, action):
            logger.info(f"{label}: {message}")
            return action()

        pipeline = AlignmentPipeline()
        with tempfile.TemporaryDirectory(prefix="aeneas_bible_") as temp_dir_name:
            alignment = pipeline.run(
                audio_path,
                transcript,
                language_code,
                "bible",
                Path(temp_dir_name),
                run_stage,
            )

        output_path = audio_path.with_suffix(OUTPUT_SUFFIX)
        JsonConverter.save(alignment, output_path)
        logger.info(f"{label}: saved to {output_path}")

        return ChapterResult(
            book_name=book_name,
            chapter_number=chapter_number,
            label=label,
            success=True,
            output_path=str(output_path),
            log_lines=log_lines,
        )

    except AlignmentError as exc:
        logger.error(f"{label} failed: {exc}")
        return ChapterResult(
            book_name=book_name,
            chapter_number=chapter_number,
            label=label,
            success=False,
            error=str(exc),
            log_lines=log_lines,
        )
    except Exception as exc:  # noqa: BLE001 - reported to the parent, not raised
        logger.exception(f"{label}: unexpected error")
        return ChapterResult(
            book_name=book_name,
            chapter_number=chapter_number,
            label=label,
            success=False,
            error=f"unexpected error: {exc}",
            log_lines=log_lines,
        )
    finally:
        logger.removeHandler(handler)
