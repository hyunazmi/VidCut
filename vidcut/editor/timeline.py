"""Timeline model of VidCut: one video, cut into clips that play one after the other.

Pure Python, no Qt, so it can be unit tested on its own.

A clip is a range [start, end) in seconds of the video. Cut (split) divides the clip at the playhead in two.
Delete removes a clip and the clips after it move forward, so the timeline never has gaps: it is always the
kept clips joined together. Every edit is one undo step.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, List, Optional, Tuple

MIN_CLIP_LENGTH = 0.05
_EPS = 1e-6


@dataclass(frozen=True)
class Source:
    path: str
    duration: float
    has_audio: bool = True
    channels: int = 0  # 0 when unknown
    sample_rate: int = 0  # 0 when unknown


@dataclass(frozen=True)
class Clip:
    start: float  # seconds in the video
    end: float

    @property
    def length(self) -> float:
        return self.end - self.start


_State = Tuple[Clip, ...]


class TimelineModel:
    def __init__(self) -> None:
        self._source: Optional[Source] = None
        self._clips: _State = ()
        self._undo: List[_State] = []
        self._redo: List[_State] = []
        self._listeners: List[Callable[[], None]] = []

    # ---- observers --------------------------------------------------
    def on_change(self, fn: Callable[[], None]) -> None:
        self._listeners.append(fn)

    def _notify(self) -> None:
        for fn in list(self._listeners):
            fn()

    # ---- state ------------------------------------------------------
    def load(self, path: str, duration: float, has_audio: bool = True, channels: int = 0, sample_rate: int = 0) -> None:
        """Start a new project with one video. A duration of 0 gives an empty timeline."""
        duration = max(0.0, duration)
        self._source = Source(path, duration, has_audio, channels, sample_rate)
        self._clips = (Clip(0.0, duration),) if duration > 0 else ()
        self._undo.clear()
        self._redo.clear()
        self._notify()

    @property
    def source(self) -> Optional[Source]:
        return self._source

    @property
    def clips(self) -> Tuple[Clip, ...]:
        return self._clips

    @property
    def total(self) -> float:
        """Length of the timeline: the kept clips, one after the other."""
        return sum(c.length for c in self._clips)

    def offsets(self) -> List[float]:
        """Where each clip starts on the timeline."""
        out, acc = [], 0.0
        for c in self._clips:
            out.append(acc)
            acc += c.length
        return out

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    # ---- lookup -----------------------------------------------------
    def index_at(self, t: float) -> Optional[int]:
        """Index of the clip at timeline time t. t == total maps to the last clip."""
        if not self._clips:
            return None
        if t < 0:
            return 0
        acc = 0.0
        for i, c in enumerate(self._clips):
            if t < acc + c.length - _EPS:
                return i
            acc += c.length
        return len(self._clips) - 1

    def locate(self, t: float) -> Optional[Tuple[int, float]]:
        """Timeline time -> (clip index, time in the video)."""
        i = self.index_at(t)
        if i is None:
            return None
        clip = self._clips[i]
        local = min(max(t - self.offsets()[i], 0.0), clip.length)
        return i, clip.start + local

    def boundaries(self) -> List[float]:
        """Cut points on the timeline, including 0 and the total length."""
        points = [0.0]
        for off, c in zip(self.offsets(), self._clips):
            points.append(off + c.length)
        out: List[float] = []
        for point in points:
            if not out or point - out[-1] > _EPS:
                out.append(point)
        return out

    # ---- history ----------------------------------------------------
    def _commit(self, clips: _State) -> None:
        self._undo.append(self._clips)
        self._redo.clear()
        self._clips = clips
        self._notify()

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self._clips)
        self._clips = self._undo.pop()
        self._notify()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self._clips)
        self._clips = self._redo.pop()
        self._notify()
        return True

    # ---- edits ------------------------------------------------------
    def split(self, t: float) -> bool:
        """Cut the clip at timeline time t in two. False when a part would be too short."""
        loc = self.locate(t)
        if loc is None:
            return False
        i, src = loc
        c = self._clips[i]
        if src - c.start < MIN_CLIP_LENGTH or c.end - src < MIN_CLIP_LENGTH:
            return False
        self._commit(self._clips[:i] + (replace(c, end=src), replace(c, start=src)) + self._clips[i + 1 :])
        return True

    def delete(self, index: int) -> bool:
        """Remove the clip at index. The clips after it move forward."""
        if not (0 <= index < len(self._clips)):
            return False
        self._commit(self._clips[:index] + self._clips[index + 1 :])
        return True

    # ---- export -----------------------------------------------------
    def export_clips(self) -> List[Clip]:
        """The clips to export. Clips that continue each other in the video are merged into one."""
        out: List[Clip] = []
        for c in self._clips:
            if out and abs(out[-1].end - c.start) < _EPS:
                out[-1] = replace(out[-1], end=c.end)
            else:
                out.append(c)
        return out
