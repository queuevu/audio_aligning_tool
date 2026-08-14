r"""Converts Aeneas sync-map output into the Rosary alignment JSON schema.

The output schema produced here must stay byte-for-byte compatible (same
keys, same types) with the existing Rosary JSON merge tool:

{
    "text": "...",
    "duration": 123.45,
    "words": [{"word": "...", "start": 0.0, "end": 0.421}],
    "canonical_text": "...",
    "source": "aeneas",
    "aligned": true,
    "parts": [{"part": 1, "text": "..."}],
    "type": "common" | "rosary"
}

For "rosary", each part additionally carries a name and bead info. The
part-level "type" (e.g. "sign_of_cross") comes from a leading '\"name"\'
marker in the transcript, and is unrelated to the document-level "type"
field above. "is_bead" is true when the part was also marked with a leading
``\bead:N\``, with "start"/"end" set to that part's own first/last word
timings (null when "is_bead" is false):

{
    ...
    "parts": [
        {
            "part": 1, "text": "...", "type": "sign_of_cross",
            "is_bead": false, "start": null, "end": null
        },
        {
            "part": 2, "text": "...", "type": "apostle_creed",
            "is_bead": true, "start": 0.0, "end": 7.76
        }
    ],
    "type": "rosary"
}

The "bible" input type is a variant of "common": the JSON's "type" field is
still written as "common", but "parts"/"part" is replaced with
"verses"/"verse":

{
    ...
    "verses": [{"verse": 1, "text": "..."}],
    "type": "common"
}
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

from app.errors import AlignmentError
from app.text_utils import normalize_whitespace

ROSARY_TYPE = "rosary"
BIBLE_TYPE = "bible"
COMMON_TYPE = "common"


class JsonConverter:
    """Stateless helpers for building and saving the final alignment JSON."""

    @staticmethod
    def parse_sync_map(aeneas_json_path: Path) -> List[Dict[str, object]]:
        """Parse an Aeneas sync-map JSON file into ordered fragment entries.

        Each entry is ``{"text": ..., "start": ..., "end": ...}``. Empty
        HEAD/TAIL fragments are ignored. Used for both the coarse
        (part-level) and fine (word-level) alignment passes.
        """
        try:
            with open(aeneas_json_path, "r", encoding="utf-8") as handle:
                sync_map = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise AlignmentError(
                f"Could not read the Aeneas output file: {exc}"
            ) from exc

        entries: List[Dict[str, object]] = []
        for fragment in sync_map.get("fragments", []):
            lines = fragment.get("lines", [])
            text = " ".join(line for line in lines if line).strip()
            if not text:
                continue  # Ignore empty HEAD/TAIL fragments.

            entries.append(
                {
                    "text": text,
                    "start": round(float(fragment.get("begin", 0.0)), 3),
                    "end": round(float(fragment.get("end", 0.0)), 3),
                }
            )
        return entries

    @staticmethod
    def convert_aeneas_output(
        aeneas_json_path: Path, expected_word_count: int
    ) -> Tuple[List[Dict[str, object]], bool]:
        """Parse an Aeneas sync-map JSON file into a list of aligned words.

        Each Aeneas fragment corresponds to exactly one word, since the
        input text file has one word per line. Returns ``(words, counts_match)``.
        """
        entries = JsonConverter.parse_sync_map(aeneas_json_path)
        words = [
            {"word": entry["text"], "start": entry["start"], "end": entry["end"]}
            for entry in entries
        ]
        counts_match = len(words) == expected_word_count
        return words, counts_match

    @staticmethod
    def apply_bead_timings(
        parts: List[Dict[str, object]],
        part_word_ranges: List[Tuple[int, int]],
        words: List[Dict[str, object]],
    ) -> None:
        """Set "is_bead"'s start/end timings in place for each rosary part.

        ``part_word_ranges`` gives each part's ``(start_index, end_index)``
        exclusive slice into ``words``, in the same order as ``parts``. A
        part flagged "is_bead" gets its own first word's start time and its
        own last word's end time; non-bead parts get ``None``/``None``.
        """
        for part, (start_index, end_index) in zip(parts, part_word_ranges):
            if part.get("is_bead") and end_index > start_index:
                part["start"] = round(words[start_index]["start"], 3)
                part["end"] = round(words[end_index - 1]["end"], 3)
            else:
                part["is_bead"] = bool(part.get("is_bead"))
                part["start"] = None
                part["end"] = None

    @staticmethod
    def build_final_alignment(
        raw_text: str,
        parts: List[Dict[str, object]],
        words: List[Dict[str, object]],
        prayer_type: str,
    ) -> Dict[str, object]:
        """Assemble the final alignment JSON structure."""
        duration = words[-1]["end"] if words else 0.0
        normalized_text = normalize_whitespace(raw_text)

        alignment = {
            "text": normalized_text,
            "duration": round(duration, 3),
            "words": words,
            "canonical_text": normalized_text,
            "source": "aeneas",
            "aligned": True,
        }

        if prayer_type == BIBLE_TYPE:
            alignment["verses"] = [
                {"verse": part["part"], "text": part["text"]} for part in parts
            ]
            alignment["type"] = COMMON_TYPE
        else:
            alignment["parts"] = parts
            alignment["type"] = prayer_type

        return alignment

    @staticmethod
    def save(alignment: Dict[str, object], output_path: Path) -> None:
        """Write the alignment JSON to disk, raising AlignmentError on failure."""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(alignment, handle, ensure_ascii=False, indent=4)
        except OSError as exc:
            raise AlignmentError(f"Could not save the JSON file: {exc}") from exc
