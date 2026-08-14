"""WAV audio helpers used to slice per-part audio segments.

Uses the stdlib ``wave`` module directly since this tool only ever
handles WAV input, so no ffmpeg dependency is needed just to cut clips.
"""

import wave
from pathlib import Path


def get_wav_duration(wav_path: Path) -> float:
    """Return the duration of a WAV file in seconds."""
    with wave.open(str(wav_path), "rb") as handle:
        return handle.getnframes() / float(handle.getframerate())


def slice_wav(src_path: Path, dest_path: Path, start: float, end: float) -> None:
    """Write the ``[start, end]`` second range of ``src_path`` to ``dest_path``."""
    with wave.open(str(src_path), "rb") as src:
        params = src.getparams()
        rate = src.getframerate()

        start_frame = max(0, int(start * rate))
        end_frame = min(src.getnframes(), int(end * rate))

        src.setpos(start_frame)
        frames = src.readframes(max(0, end_frame - start_frame))

    with wave.open(str(dest_path), "wb") as dest:
        dest.setparams(params)
        dest.writeframes(frames)
