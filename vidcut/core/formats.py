"""File format constants used by the editor."""

from __future__ import annotations

import os

OUTPUT_EXTS = ("mp4", "mkv", "mov")
VIDEO_EXTS = ("3gp", "avi", "flv", "m2ts", "m4v", "mkv", "mov", "mp4", "mpeg", "mpg", "mts", "ts", "webm", "wmv")


def extension(path: str) -> str:
    """Lower-case extension without the dot ('' if there is none)."""
    return os.path.splitext(path)[1].lstrip(".").lower()


def is_video_file(path: str) -> bool:
    return extension(path) in VIDEO_EXTS


def default_output_extension(source_path: str) -> str:
    """Keep the source container when it is a supported output, otherwise use mp4."""
    ext = extension(source_path)
    return ext if ext in OUTPUT_EXTS else "mp4"
