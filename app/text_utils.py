"""Pure text-processing helpers shared by the alignment pipeline.

These functions have no GUI or Aeneas dependencies, which keeps them easy
to reason about and reuse (e.g. from tests).
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Matches a standalone "\bead:<n>\" marker token, e.g. \bead:1\, \bead:2\.
BEAD_MARKER_PATTERN = re.compile(r"\\bead:(\d+)\\")

# Matches a standalone '\"<name>"\' marker token, e.g. \"sign_of_cross"\.
# The quote character is matched loosely (straight " or curly “/”) since
# text editors/autocorrect often turn straight quotes into curly ones, and
# the two sides don't have to be the same character.
_QUOTE_CHARS = "\"\u201c\u201d"
TYPE_MARKER_PATTERN = re.compile(
    rf"\\[{_QUOTE_CHARS}](\w+)[{_QUOTE_CHARS}]\\"
)

# Either marker, used when stripping them out of the transcript wholesale.
ROSARY_MARKER_PATTERN = re.compile(
    "|".join(p.pattern for p in (BEAD_MARKER_PATTERN, TYPE_MARKER_PATTERN))
)


def strip_rosary_markers(raw_text: str) -> str:
    """Remove ``\\bead:N\\`` and ``\\"name"\\`` marker tokens from ``raw_text``.

    Both markers are tokens the user drops at the start of a part: the bead
    marker flags it as a rosary bead (e.g. ``\\bead:1\\In the name...``), the
    type marker names it (e.g. ``\\"sign_of_cross"\\In the name...``). Either
    may sit on their own, or be glued directly onto the following word with
    no space. They must never reach Aeneas or appear in the final
    "text"/"words" output, so this strips them out before any parts/words
    splitting happens.

    Lines that contain only marker tokens are dropped entirely rather than
    left blank, so a marker on its own line never introduces a spurious
    blank-line part separator.
    """
    normalised = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalised.split("\n")

    cleaned_lines: List[str] = []

    for line in lines:
        if not line.strip():
            cleaned_lines.append("")  # Preserve genuine blank-line separators.
            continue

        # Replace each marker with a single space (rather than deleting it
        # outright) so a marker glued directly onto a word doesn't fuse that
        # word with whatever precedes/follows it.
        replaced_line = ROSARY_MARKER_PATTERN.sub(" ", line)
        kept_tokens = replaced_line.split()

        if kept_tokens:
            cleaned_lines.append(" ".join(kept_tokens))
        # else: line held only marker(s) - drop it, don't add a blank line.

    return "\n".join(cleaned_lines)


def parse_rosary_parts(raw_text: str) -> Tuple[str, List[Dict[str, object]]]:
    """Split ``raw_text`` into parts, flagging each as a bead and naming its type.

    A part is a rosary bead when its first non-blank line starts with a
    ``\\bead:N\\`` marker (the number itself isn't retained - it's only used
    to mark the part). Right after that (or at the very start, if there's no
    bead marker), a ``\\"name"\\`` marker names the part's "type". Markers are
    stripped from the returned part text, and from the returned
    ``cleaned_text``, same as ``strip_rosary_markers``.

    Returns ``(cleaned_text, parts)`` where each part is
    ``{"part": n, "text": ..., "type": str | None, "is_bead": bool}``.
    """
    normalised = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    raw_blocks = re.split(r"\n\s*\n", normalised.strip("\n"))

    is_bead_flags: List[bool] = []
    part_types: List[Optional[str]] = []
    for block in raw_blocks:
        block_text = block.strip()
        if not block_text:
            continue

        bead_match = BEAD_MARKER_PATTERN.match(block_text)
        is_bead_flags.append(bool(bead_match))
        remainder = block_text[bead_match.end() :] if bead_match else block_text

        type_match = TYPE_MARKER_PATTERN.match(remainder)
        part_types.append(type_match.group(1) if type_match else None)

    cleaned_text = strip_rosary_markers(raw_text)
    parts = parse_parts(cleaned_text)

    if len(parts) != len(is_bead_flags):
        raise ValueError(
            "Rosary marker parsing produced a different part count "
            f"({len(is_bead_flags)}) than the cleaned transcript "
            f"({len(parts)}). Check for a part made up only of marker(s)."
        )

    for part, is_bead, part_type in zip(parts, is_bead_flags, part_types):
        part["type"] = part_type
        part["is_bead"] = is_bead

    return cleaned_text, parts


def parse_parts(raw_text: str) -> List[Dict[str, object]]:
    """Split raw text into logical parts, using blank lines as separators.

    Returns a list of ``{"part": n, "text": part_text}`` dictionaries.
    Only blank lines are treated as separators; punctuation is ignored,
    and internal formatting within a part is preserved exactly as typed.
    """
    normalised = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", normalised.strip("\n"))

    parts: List[Dict[str, object]] = []
    part_number = 0
    for block in blocks:
        block_text = block.strip()
        if not block_text:
            continue
        part_number += 1
        parts.append({"part": part_number, "text": block_text})
    return parts


def normalize_whitespace(text: str) -> str:
    """Collapse any run of whitespace (spaces, tabs, newlines) to one space."""
    return re.sub(r"\s+", " ", text).strip()


def build_words_file(raw_text: str, words_file_path: Path) -> int:
    """Write one word per line to ``words_file_path`` using ``str.split()``.

    Punctuation stays attached to each word because ``str.split()`` only
    splits on whitespace. Returns the number of words written.
    """
    words = raw_text.split()
    with open(words_file_path, "w", encoding="utf-8") as handle:
        for word in words:
            handle.write(word + "\n")
    return len(words)


def build_parts_file(parts: List[Dict[str, object]], parts_file_path: Path) -> None:
    """Write one line per part to ``parts_file_path`` for a coarse alignment pass.

    Aligning each part against the full audio first (before aligning its
    individual words against a short slice) keeps DTW drift from
    accumulating across the whole file.
    """
    with open(parts_file_path, "w", encoding="utf-8") as handle:
        for part in parts:
            handle.write(normalize_whitespace(str(part["text"])) + "\n")
