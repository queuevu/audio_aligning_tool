"""Discovers chapter text/audio pairs for the Bible batch alignment tool.

Two input layouts are supported and auto-detected.

Single book - the given folders directly contain the chapters::

    <text_folder>/
        Chapter1.txt
        Chapter2.txt
        ...

    <audio_folder>/
        Chapter1/
            Enceladus-Book_Name-Chapter_1.wav
        Chapter2/
            Enceladus-Book_Name-Chapter_2.wav
        ...

Whole Bible - the given folders contain one subfolder per book, each laid
out like the single-book case above::

    <text_folder>/
        Genesis/
            Chapter1.txt
            ...
        Exodus/
            Chapter1.txt
            ...

    <audio_folder>/
        Genesis/
            Genesis_Chapter_1/
                Blossom_Genesis_Chapter1.wav
            ...
        Exodus/
            ...

Chapters are matched by number (parsed out of the file/folder name, not by
exact name) and books are matched by folder name (case-insensitive), since
the audio side's own naming conventions differ from the text side's.
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
    book_name: str = ""  # Set when discovered as part of a whole-Bible scan.


@dataclass
class BookJob:
    """One book folder matched between the text and audio roots."""

    book_name: str
    text_folder: Path
    audio_folder: Path


def _chapter_number(name: str) -> Optional[int]:
    match = CHAPTER_NUMBER_PATTERN.search(name)
    return int(match.group(1)) if match else None


def discover_chapters(
    text_folder: Path, audio_folder: Path, book_name: str = ""
) -> Tuple[List[ChapterJob], List[str]]:
    """Pair up chapter text files with their chapter audio folders.

    Returns ``(jobs, problems)``. ``jobs`` is sorted by chapter number.
    ``problems`` is a list of human-readable strings describing any chapter
    that couldn't be matched (missing audio folder, no .wav file inside it).
    """
    prefix = f"{book_name}: " if book_name else ""

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
                f"{prefix}Chapter {chapter_number}: no matching audio folder "
                f"found for '{text_path.name}'."
            )
            continue

        wav_files = sorted(audio_dir.glob("*.wav"))
        if not wav_files:
            problems.append(
                f"{prefix}Chapter {chapter_number}: '{audio_dir.name}' has "
                "no .wav file."
            )
            continue

        jobs.append(
            ChapterJob(
                chapter_number=chapter_number,
                text_path=text_path,
                audio_path=wav_files[0],
                ambiguous_audio=len(wav_files) > 1,
                book_name=book_name,
            )
        )

    return jobs, problems


def discover_books(text_root: Path, audio_root: Path) -> Tuple[List[BookJob], List[str]]:
    """Pair up book folders under ``text_root`` and ``audio_root`` by name."""
    audio_dirs_by_name = {
        path.name.lower(): path for path in audio_root.iterdir() if path.is_dir()
    }

    jobs: List[BookJob] = []
    problems: List[str] = []

    for text_book_dir in sorted(p for p in text_root.iterdir() if p.is_dir()):
        audio_book_dir = audio_dirs_by_name.get(text_book_dir.name.lower())
        if audio_book_dir is None:
            problems.append(
                f"Book '{text_book_dir.name}': no matching audio folder found."
            )
            continue
        jobs.append(BookJob(text_book_dir.name, text_book_dir, audio_book_dir))

    return jobs, problems


def discover_jobs(
    text_root: Path, audio_root: Path
) -> Tuple[List[ChapterJob], List[str]]:
    """Discover chapters under ``text_root``/``audio_root``, either layout.

    Auto-detects which layout is in play: if ``text_root`` directly contains
    chapter ``.txt`` files it's treated as a single book, otherwise as a
    whole-Bible root containing one subfolder per book.
    """
    if any(text_root.glob("*.txt")):
        return discover_chapters(text_root, audio_root)

    books, problems = discover_books(text_root, audio_root)

    all_jobs: List[ChapterJob] = []
    for book in books:
        book_jobs, book_problems = discover_chapters(
            book.text_folder, book.audio_folder, book.book_name
        )
        all_jobs.extend(book_jobs)
        problems.extend(book_problems)

    return all_jobs, problems
