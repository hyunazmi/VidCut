"""Finds the ffmpeg and ffprobe that are installed on the system.

VidCut does not ship its own copy of FFmpeg and does not install one with pip. The search order is:

    1. the folder chosen in the Settings tab
    2. the folder in the environment variable VIDCUT_FFMPEG_DIR
    3. the folders of the system PATH (this also finds them on Windows, through PATHEXT)
    4. on macOS, the usual Homebrew and MacPorts folders, because an app started from Finder
       does not always get the PATH of the terminal
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import List

TOOL_NAMES = ("ffmpeg", "ffprobe")
_MACOS_EXTRA_DIRS = ("/opt/homebrew/bin", "/usr/local/bin", "/opt/local/bin")


@dataclass(frozen=True)
class FfmpegTools:
    ffmpeg: str = ""
    ffprobe: str = ""

    def is_valid(self) -> bool:
        return bool(self.ffmpeg and self.ffprobe)


def _exe_names(name: str) -> List[str]:
    if sys.platform != "win32":
        return [name]
    exts = [e.lower() for e in os.environ.get("PATHEXT", ".EXE").split(";") if e]
    return [name + e for e in exts] or [name + ".exe"]


def _which_in(name: str, directory: str) -> str:
    for candidate in _exe_names(name):
        path = os.path.join(directory, candidate)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return os.path.abspath(path)
    return ""


def resolve_tools_dir(text: str) -> str:
    """Turn user input into a folder: accepts a folder, or the path of ffmpeg / ffprobe itself."""
    path = os.path.expanduser(text.strip())
    if not path:
        return ""
    if os.path.isfile(path):
        path = os.path.dirname(path)
    return os.path.abspath(path)


def missing_tools(directory: str) -> List[str]:
    """Names of the required programs that are not executable files in directory."""
    return [name for name in TOOL_NAMES if not _which_in(name, directory)]


def find_in_dir(directory: str) -> FfmpegTools:
    if not directory:
        return FfmpegTools()
    ff = _which_in("ffmpeg", directory)
    fp = _which_in("ffprobe", directory)
    if ff and fp:
        return FfmpegTools(ff, fp)
    return FfmpegTools()


def _path_dirs() -> List[str]:
    return [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]


def locate(custom_dir: str = "") -> FfmpegTools:
    """The first folder that holds both programs, in the search order above."""
    dirs: List[str] = []
    if custom_dir:
        dirs.append(custom_dir)
    dirs += _path_dirs()
    if sys.platform == "darwin":
        dirs += list(_MACOS_EXTRA_DIRS)

    seen = set()
    for directory in dirs:
        normalized = os.path.normcase(os.path.normpath(directory))
        if normalized in seen:
            continue
        seen.add(normalized)
        tools = find_in_dir(directory)
        if tools.is_valid():
            return tools

    # ffmpeg and ffprobe may sit in different folders of the PATH: take the first of each.
    path_dirs = _path_dirs()
    ff = next((f for f in (_which_in("ffmpeg", d) for d in path_dirs) if f), "")
    fp = next((f for f in (_which_in("ffprobe", d) for d in path_dirs) if f), "")
    if ff and fp:
        return FfmpegTools(ff, fp)
    return FfmpegTools()
