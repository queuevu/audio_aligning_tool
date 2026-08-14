"""Thin wrapper around the official Aeneas command-line entry point.

We deliberately invoke ``aeneas.tools.execute_task.ExecuteTaskCLI`` (the
same class the ``aeneas_execute_task`` console script uses) instead of
calling lower-level alignment APIs directly, so behaviour matches the
official CLI exactly.
"""

import io
import sys
from pathlib import Path

from aeneas.tools.execute_task import ExecuteTaskCLI

from app.errors import AlignmentError


class AeneasRunner:
    """Runs a single Aeneas alignment task and produces a JSON sync map."""

    def run(
        self,
        audio_path: Path,
        words_path: Path,
        output_json_path: Path,
        language_code: str,
    ) -> None:
        """Align ``audio_path`` against ``words_path`` (one word per line).

        Writes the resulting sync map to ``output_json_path``. Raises
        ``AlignmentError`` with a user-friendly message on any failure.
        """
        config_string = (
            f"task_language={language_code}|"
            "is_text_type=plain|os_task_file_format=json"
        )

        arguments = [
            "execute_task",
            str(audio_path),
            str(words_path),
            config_string,
            str(output_json_path),
        ]

        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        original_stdout, original_stderr = sys.stdout, sys.stderr

        try:
            sys.stdout, sys.stderr = stdout_buffer, stderr_buffer
            cli = ExecuteTaskCLI(use_sys=False)
            exit_code = cli.run(arguments=arguments)
        except Exception as exc:  # noqa: BLE001 - convert any aeneas failure
            raise AlignmentError(
                "Aeneas raised an unexpected error while aligning the "
                f"audio and text: {exc}"
            ) from exc
        finally:
            sys.stdout, sys.stderr = original_stdout, original_stderr

        if exit_code != 0 or not output_json_path.exists():
            log_output = (
                stdout_buffer.getvalue() + "\n" + stderr_buffer.getvalue()
            ).strip()
            details = log_output[-1500:] if log_output else "(no output captured)"
            raise AlignmentError(
                "Aeneas failed to align the audio and text.\n"
                f"Exit code: {exit_code}\n"
                f"Details:\n{details}"
            )
