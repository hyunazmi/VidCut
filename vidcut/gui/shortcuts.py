"""Keyboard shortcuts: the single place that defines keys, labels and tooltips.

This module does not import Qt, so it can be unit tested without PySide6.
Keys use Qt's portable text format, for example "Ctrl+Shift+Z". The list is also the reference for README.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

FAR_STEP_FRAMES = 10  # how far the Up and Down keys move, in frames
JUMP_SECONDS = 5.0  # how far Shift+Left and Shift+Right move


@dataclass(frozen=True)
class Shortcut:
    id: str
    label: str
    keys: Tuple[str, ...]
    tip: str
    hint: str = ""  # shown in brackets in tooltips, e.g. "Cut (C)"


SHORTCUTS: Tuple[Shortcut, ...] = (
    Shortcut("open", "Open", ("Ctrl+O",), "Open a video", hint="Ctrl+O"),
    Shortcut("export", "Export", ("Ctrl+E",), "Export the edited video", hint="Ctrl+E"),
    Shortcut("play", "Play / Pause", ("Space",), "Play or pause the preview"),
    Shortcut("cut", "Cut", ("C",), "Split the clip at the playhead", hint="C"),
    Shortcut("delete", "Delete clip", ("Delete", "Backspace"), "Delete the clip under the playhead", hint="Del"),
    Shortcut("undo", "Undo", ("Ctrl+Z",), "Undo the last edit", hint="Ctrl+Z"),
    Shortcut("redo", "Redo", ("Ctrl+Y", "Ctrl+Shift+Z"), "Redo the last undone edit", hint="Ctrl+Y"),
    Shortcut("step_back", "Back one frame", ("Left",), "Back one frame"),
    Shortcut("step_forward", "Forward one frame", ("Right",), "Forward one frame"),
    Shortcut("far_back", f"Back {FAR_STEP_FRAMES} frames", ("Down",), f"Back {FAR_STEP_FRAMES} frames"),
    Shortcut("far_forward", f"Forward {FAR_STEP_FRAMES} frames", ("Up",), f"Forward {FAR_STEP_FRAMES} frames"),
    Shortcut("jump_back", "Back 5 seconds", ("Shift+Left",), "Back five seconds"),
    Shortcut("jump_forward", "Forward 5 seconds", ("Shift+Right",), "Forward five seconds"),
    Shortcut("prev_cut", "Previous cut", ("Ctrl+Left",), "Jump to the previous cut"),
    Shortcut("next_cut", "Next cut", ("Ctrl+Right",), "Jump to the next cut"),
    Shortcut("go_start", "Go to start", ("S", "Home"), "Go to the start of the video"),
    Shortcut("go_end", "Go to end", ("E", "End"), "Go to the end of the video"),
    Shortcut("go_to_time", "Go to time", ("Ctrl+G",), "Type a time to jump to"),
    Shortcut("zoom_in", "Zoom in", ("=", "+"), "Zoom the timeline in"),
    Shortcut("zoom_out", "Zoom out", ("-",), "Zoom the timeline out"),
    Shortcut("zoom_fit", "Fit timeline", ("0",), "Fit the whole timeline in the window"),
)

# Shortcuts that also work when no video is loaded. All the others only work with a video in the Editor.
GLOBAL_IDS = frozenset({"open"})


def by_id() -> Dict[str, Shortcut]:
    return {s.id: s for s in SHORTCUTS}


def button_text(shortcut: Shortcut) -> str:
    return f"{shortcut.label} ({shortcut.hint})" if shortcut.hint else shortcut.label
