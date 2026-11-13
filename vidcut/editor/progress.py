"""Turns the many small progress reports of an export into one percentage and one sentence.

An export has up to two phases: cutting the video (one or more parts) and joining the parts. Each phase
gets a share of the bar.
"""

from __future__ import annotations

import re
import time
from typing import Callable, Dict, Optional

VIDEO, MERGE = "video", "merge"
_WEIGHTS = {VIDEO: 92.0, MERGE: 8.0}
_PREPARING_SHARE = 0.2  # a "preparing" step has no step count, so it gets a small slice
_ETA_MIN_PROGRESS = 0.03  # too early to guess the remaining time before this
_PHASE_DETAIL = {MERGE: "Putting the parts together without re-encoding"}


def clean_step_label(label: str) -> str:
    """Make an engine step label readable: "[A] Re-encoding 0.8s (start)..." becomes "Re-encoding 0.8s (start)"."""
    text = re.sub(r"^\[[A-Z]\]\s*", "", label.strip())
    text = re.sub(r"^Preparing:\s*", "", text)
    return text.rstrip(". ").strip()


class ProgressTracker:
    def __init__(self, parts: int, merge: bool, clock: Callable[[], float] = time.monotonic) -> None:
        self._parts = max(1, parts)
        self._clock = clock
        phases = [VIDEO] + ([MERGE] if merge else [])
        total = sum(_WEIGHTS[p] for p in phases)
        self._weights: Dict[str, float] = {p: _WEIGHTS[p] / total for p in phases}
        self._phases = phases
        self._phase = VIDEO
        self._part = 1
        self._step_index = 0
        self._step_count = 0
        self._fraction = 0.0
        self._detail = ""
        self._best = 0.0
        self._started: Optional[float] = None

    # ---- events -----------------------------------------------------
    def start_part(self, index: int) -> None:
        self._begin()
        self._phase, self._part = VIDEO, max(1, min(index, self._parts))
        self._step_index = self._step_count = 0
        self._fraction = 0.0
        self._detail = ""

    def start_step(self, index: int, count: int, label: str = "") -> None:
        """A step inside the current part. A count of 0 means a preparation step."""
        self._begin()
        self._step_index, self._step_count = index, count
        self._fraction = 0.0
        if label:
            self._detail = clean_step_label(label)

    def set_fraction(self, fraction: float) -> None:
        self._begin()
        self._fraction = min(max(fraction, 0.0), 1.0)

    def start_merge(self) -> None:
        self._begin()
        self._phase = MERGE
        self._fraction = 0.0
        self._detail = _PHASE_DETAIL[MERGE]

    def _begin(self) -> None:
        if self._started is None:
            self._started = self._clock()

    # ---- results ----------------------------------------------------
    @property
    def overall(self) -> float:
        """Progress of the whole export from 0.0 to 1.0. It never goes backwards."""
        done = 0.0
        for phase in self._phases:
            if phase == self._phase:
                break
            done += self._weights[phase]
        if self._phase == VIDEO:
            if self._step_count > 0:
                part = (self._step_index - 1 + self._fraction) / self._step_count
            else:
                part = self._fraction * _PREPARING_SHARE
            phase_fraction = (self._part - 1 + part) / self._parts
        else:
            phase_fraction = self._fraction
        value = done + self._weights[self._phase] * phase_fraction
        self._best = max(self._best, min(value, 1.0))
        return self._best

    @property
    def current_part(self) -> int:
        """The part being cut (1-based). While the parts are joined, this is the last one."""
        return self._parts if self._phase == MERGE else self._part

    @property
    def part_count(self) -> int:
        return self._parts

    @property
    def label(self) -> str:
        if self._phase == MERGE:
            return "Joining the parts"
        preparing = self._step_count == 0  # reading the file, looking for keyframes, planning
        if self._parts == 1:
            return "Preparing the export" if preparing else "Cutting the video"
        verb = "Preparing" if preparing else "Cutting"
        return f"{verb} part {self._part} of {self._parts}"

    @property
    def detail(self) -> str:
        """What the current step is doing, for example "Looking for keyframes"."""
        return self._detail

    @property
    def eta(self) -> float:
        """Estimated seconds left, or -1.0 when it is too early to tell."""
        progress = self.overall
        if self._started is None or progress < _ETA_MIN_PROGRESS:
            return -1.0
        elapsed = self._clock() - self._started
        return max(0.0, elapsed * (1.0 - progress) / progress)
