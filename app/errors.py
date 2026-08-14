"""Custom exceptions used across the application."""


class AlignmentError(Exception):
    """Raised for any user-facing failure during the alignment pipeline.

    The message on this exception is always safe to show directly to the
    user (no Python traceback), so it is what the GUI displays in error
    dialogs.
    """
