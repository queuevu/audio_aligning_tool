# Audio Aligning Tool

A desktop app (PySide6 + [aeneas](https://github.com/readbeyond/aeneas)) for
forced-aligning audio recordings to transcripts and exporting word/phrase
timing as JSON. Includes a single-file tool and a Bible batch-alignment tool.

## Setup

Requirements:
- macOS with [Homebrew](https://brew.sh)
- `python3.10` on PATH (aeneas requires 3.10): `brew install python@3.10`
- `espeak-ng` and `ffmpeg`: `brew install espeak-ng ffmpeg`

No manual virtual environment setup needed — just run the app and it sets
itself up on first use:

```bash
./run.sh
```

This creates `.venv` and installs everything from `requirements.txt`
(PySide6, aeneas, numpy) automatically the first time it's run. Subsequent
runs reuse the existing `.venv`.

To re-run setup manually (e.g. after changing `requirements.txt`):

```bash
./setup.sh
```

## Running

Word Alignment Tool (default):

```bash
./run.sh
```

Bible Batch Alignment Tool:

```bash
./run.sh bible_main.py
```

In the app:
1. Browse/drag-drop a `.wav` file
2. Pick the language (English/Kannada/Tamil)
3. Paste the transcript (blank line between parts/prayers)
4. Choose an output `.json` path
5. Click Generate Alignment

## Project layout

- `main.py` — entry point for the Word Alignment Tool
- `bible_main.py` — entry point for the Bible Batch Alignment Tool
- `app/` — application code (UI windows, aeneas runner, alignment pipeline, batch processing)
- `audiogen.py` — standalone Colab script for generating TTS audio via Gemini (unrelated to the desktop app)
