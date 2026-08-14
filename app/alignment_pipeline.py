"""Core two-pass alignment pipeline, independent of any GUI/threading concern.

Both the single-file tool (``AlignmentWorker``) and the Bible batch tool
(``BibleBatchWorker``) drive this class; it has no Qt dependency so it can
run on any thread, or be called directly in a loop.
"""

from pathlib import Path
from typing import Callable, Dict, List, Tuple, TypeVar

from app.aeneas_runner import AeneasRunner
from app.audio_utils import get_wav_duration, slice_wav
from app.errors import AlignmentError
from app.json_converter import ROSARY_TYPE, JsonConverter
from app.logger import get_logger
from app.text_utils import (
    build_parts_file,
    build_words_file,
    parse_parts,
    parse_rosary_parts,
)

logger = get_logger()

_T = TypeVar("_T")

RunStage = Callable[[str, Callable[[], _T]], _T]

# Extra audio kept on either side of a part's coarse boundary before the
# fine, per-part word alignment pass, so words near the edges aren't
# clipped by a slightly-off coarse boundary.
PART_PADDING_SECONDS = 0.4


def default_run_stage(message: str, action: Callable[[], _T]) -> _T:
    """A ``RunStage`` that just logs the message and runs the action."""
    logger.info(message)
    return action()


class AlignmentPipeline:
    """Runs transcript parsing, Aeneas alignment and JSON assembly.

    Callers own progress reporting via the ``run_stage`` callback passed to
    ``run()`` - it receives a stage description and the callable to invoke,
    and must return whatever that callable returns.
    """

    def __init__(self) -> None:
        self._aeneas_runner = AeneasRunner()

    def run(
        self,
        audio_path: Path,
        transcript: str,
        language_code: str,
        prayer_type: str,
        temp_dir: Path,
        run_stage: RunStage = default_run_stage,
    ) -> Dict[str, object]:
        """Two-pass alignment: coarse part boundaries, then fine per-part words.

        Aligning words directly against the whole audio file lets DTW drift
        accumulate over the file's length, and single-word fragments are too
        short for reliable MFCC matching on their own. Confining the
        word-level pass to a short slice around each part's coarse boundary
        removes both problems. Returns the final alignment dict (unsaved).
        """
        self.audio_path = audio_path
        self.transcript = transcript
        self.language_code = language_code
        self.prayer_type = prayer_type

        parts = run_stage("Reading transcript...", self._read_transcript)

        parts_path = temp_dir / "parts.txt"
        run_stage(
            "Building coarse alignment fragments...",
            lambda: build_parts_file(parts, parts_path),
        )

        coarse_output_path = temp_dir / "aeneas_parts_output.json"
        run_stage(
            "Running coarse Aeneas pass...",
            lambda: self._aeneas_runner.run(
                self.audio_path, parts_path, coarse_output_path, self.language_code
            ),
        )

        part_bounds = JsonConverter.parse_sync_map(coarse_output_path)
        if len(part_bounds) != len(parts):
            raise AlignmentError(
                "The coarse alignment pass returned "
                f"{len(part_bounds)} segment(s) but the transcript has "
                f"{len(parts)} part(s). Check for parts with no words."
            )

        audio_duration = get_wav_duration(self.audio_path)

        words, expected_words, part_word_ranges = run_stage(
            "Running per-part word alignment...",
            lambda: self._align_words_per_part(
                parts, part_bounds, audio_duration, temp_dir
            ),
        )

        if not words:
            raise AlignmentError("Aeneas did not return any aligned words.")

        counts_match = len(words) == expected_words
        if counts_match:
            logger.info("✓ All words aligned successfully.")
        else:
            logger.warning("Warning:")
            logger.warning(f"Expected: {expected_words}")
            logger.warning(f"Aligned: {len(words)}")

        def _convert_output():
            if self.prayer_type == ROSARY_TYPE:
                JsonConverter.apply_bead_timings(parts, part_word_ranges, words)
            return JsonConverter.build_final_alignment(
                self.transcript, parts, words, self.prayer_type
            )

        return run_stage("Converting output...", _convert_output)

    def _read_transcript(self) -> list:
        if self.prayer_type == ROSARY_TYPE:
            cleaned_transcript, parts = parse_rosary_parts(self.transcript)
            self.transcript = cleaned_transcript
        else:
            parts = parse_parts(self.transcript)

        if not parts:
            raise AlignmentError("The transcript appears to be empty.")
        return parts

    def _align_words_per_part(
        self,
        parts: List[Dict[str, object]],
        part_bounds: List[Dict[str, object]],
        audio_duration: float,
        temp_dir: Path,
    ) -> Tuple[List[Dict[str, object]], int, List[Tuple[int, int]]]:
        """Align each part's words against a short slice of its own audio.

        Returns ``(words, expected_word_count, part_word_ranges)`` with word
        start/end times already offset back into the full audio's timeline.
        ``part_word_ranges`` gives each part's ``(start_index, end_index)``
        exclusive slice into ``words``, based on how many words Aeneas
        actually returned for that part (not the expected count), so it
        stays correct even if a part's alignment came back short/long.
        """
        words: List[Dict[str, object]] = []
        expected_word_count = 0
        part_word_ranges: List[Tuple[int, int]] = []

        # Midpoint of the gap between each pair of adjacent parts. Capping
        # slices at these points (instead of just padding symmetrically)
        # guarantees neighbouring parts' audio slices never overlap, so
        # their aligned words can't overlap either.
        split_points = [
            max(part_bounds[i]["end"], part_bounds[i + 1]["start"])
            if part_bounds[i + 1]["start"] < part_bounds[i]["end"]
            else (part_bounds[i]["end"] + part_bounds[i + 1]["start"]) / 2.0
            for i in range(len(part_bounds) - 1)
        ]

        for index, (part, bounds) in enumerate(zip(parts, part_bounds)):
            part_text = str(part["text"])
            part_word_count = len(part_text.split())
            expected_word_count += part_word_count
            if part_word_count == 0:
                part_word_ranges.append((len(words), len(words)))
                continue

            lower_limit = 0.0 if index == 0 else split_points[index - 1]
            upper_limit = (
                audio_duration if index == len(parts) - 1 else split_points[index]
            )

            slice_start = max(lower_limit, bounds["start"] - PART_PADDING_SECONDS)
            slice_end = min(upper_limit, bounds["end"] + PART_PADDING_SECONDS)
            slice_end = max(slice_end, slice_start)

            slice_audio_path = temp_dir / f"part_{index}.wav"
            slice_wav(self.audio_path, slice_audio_path, slice_start, slice_end)

            part_words_path = temp_dir / f"part_{index}_words.txt"
            build_words_file(part_text, part_words_path)

            part_output_path = temp_dir / f"part_{index}_output.json"
            self._aeneas_runner.run(
                slice_audio_path, part_words_path, part_output_path, self.language_code
            )

            entries = JsonConverter.parse_sync_map(part_output_path)
            if len(entries) != part_word_count:
                logger.warning(
                    f"Part {part['part']}: expected {part_word_count} words, "
                    f"aligned {len(entries)}."
                )

            range_start = len(words)
            for entry in entries:
                words.append(
                    {
                        "word": entry["text"],
                        "start": round(entry["start"] + slice_start, 3),
                        "end": round(entry["end"] + slice_start, 3),
                    }
                )
            part_word_ranges.append((range_start, len(words)))

        return words, expected_word_count, part_word_ranges
