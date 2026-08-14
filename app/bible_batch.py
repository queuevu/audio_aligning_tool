"""Discovers chapter text/audio pairs for the Bible batch alignment tool.

Expected layout::

    <text_folder>/book_name/
        Chapter1.txt
        Chapter2.txt
        ...

    <audio_folder>/book_name/
        Chapter1/
            Enceladus-Book_Name-Chapter_1.wav
        Chapter2/
            Enceladus-Book_Name-Chapter_2.wav
        ...

Chapters are matched by number (parsed out of the file/folder name), not by
exact name, since the audio file's own naming convention differs from the
chapter folder's.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

CHAPTER_NUMBER_PATTERN = re.compile(r"chapter[_\s]*0*(\d+)", re.IGNORECASE)


@dataclass
class ChapterJob:
    """One chapter ready to be aligned: its text file and matching audio file."""

    chapter_number: int
    text_path: Path
    audio_path: Path
    ambiguous_audio: bool  # True if the audio folder had more than one .wav


def _chapter_number(name: str) -> Optional[int]:
    match = CHAPTER_NUMBER_PATTERN.search(name)
    return int(match.group(1)) if match else None


def discover_chapters(
    text_folder: Path, audio_folder: Path
) -> Tuple[List[ChapterJob], List[str]]:
    """Pair up chapter text files with their chapter audio folders.

    Returns ``(jobs, problems)``. ``jobs`` is sorted by chapter number.
    ``problems`` is a list of human-readable strings describing any chapter
    that couldn't be matched (missing audio folder, no .wav file inside it).
    """
    text_files = {}
    for path in sorted(text_folder.glob("*.txt")):
        number = _chapter_number(path.stem)
        if number is not None:
            text_files[number] = path

    audio_dirs = {}
    for path in sorted(p for p in audio_folder.iterdir() if p.is_dir()):
        number = _chapter_number(path.name)
        if number is not None:
            audio_dirs[number] = path

    jobs: List[ChapterJob] = []
    problems: List[str] = []

    for chapter_number in sorted(text_files):
        text_path = text_files[chapter_number]
        audio_dir = audio_dirs.get(chapter_number)

        if audio_dir is None:
            problems.append(
                f"Chapter {chapter_number}: no matching audio folder found "
                f"for '{text_path.name}'."
            )
            continue

        wav_files = sorted(audio_dir.glob("*.wav"))
        if not wav_files:
            problems.append(
                f"Chapter {chapter_number}: '{audio_dir.name}' has no .wav file."
            )
            continue

        jobs.append(
            ChapterJob(
                chapter_number=chapter_number,
                text_path=text_path,
                audio_path=wav_files[0],
                ambiguous_audio=len(wav_files) > 1,
            )
        )

    return jobs, problems
