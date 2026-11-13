"""Runs a whole export: cut the video (one or several parts, joined if there are several).

It looks like one job to the caller. It reports a single overall percentage, the part it is on, one sentence
about what it is doing, and one result, instead of the separate reports of each ffmpeg step.
"""

from __future__ import annotations

import os
import time
from typing import Optional

from ..core.time_utils import format_size, format_time
from ..engine.events import Signal
from ..engine.smart_cutter import BatchCutter, SmartCutter
from .progress import ProgressTracker


class ExportPipeline:
    stage_changed = Signal(str, int, int)  # the phase as a sentence, the part (1-based), the number of parts
    detail_changed = Signal(str)  # the step inside it ("Looking for keyframes")
    progress = Signal(float, float)  # overall fraction 0..1, seconds left (-1 if unknown)
    succeeded = Signal(str)  # details to show the user
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, cutter: SmartCutter, parts: int, output: str = "", duration: float = 0.0) -> None:
        self._cutter = cutter
        self._parts = parts
        self._output = output
        self._duration = duration
        self._cancel_requested = False
        self._last_label: Optional[tuple] = None
        self._last_detail = ""

    @property
    def output(self) -> str:
        return self._output

    def request_cancel(self) -> None:
        self._cancel_requested = True
        self._cutter.request_cancel()

    def run(self) -> None:
        started = time.monotonic()
        tracker = ProgressTracker(self._parts, merge=self._parts > 1)
        outcome: dict = {}
        self._connect_cutter(tracker, outcome)

        self._report(tracker)
        self._cutter.run()
        if "cancelled" in outcome or self._cancel_requested:
            self.cancelled.emit()
            return
        if "failed" in outcome:
            self.failed.emit(outcome["failed"])
            return

        tracker.set_fraction(1.0)
        self.progress.emit(1.0, 0.0)
        self.succeeded.emit(self._summary(time.monotonic() - started))

    # ---- internals --------------------------------------------------
    def _connect_cutter(self, tracker: ProgressTracker, outcome: dict) -> None:
        cutter = self._cutter
        cutter.stage_changed.connect(lambda label, index, count: self._on_step(tracker, label, index, count))
        cutter.progress.connect(lambda fraction, _speed, _eta: self._on_fraction(tracker, fraction))
        cutter.succeeded.connect(lambda text: outcome.__setitem__("ok", text))
        cutter.failed.connect(lambda text: outcome.__setitem__("failed", text))
        cutter.cancelled.connect(lambda: outcome.__setitem__("cancelled", True))
        if isinstance(cutter, BatchCutter):  # several parts, then a join
            cutter.clip_started.connect(lambda index, _count, _name: self._on_part(tracker, index))
            cutter.merge_started.connect(lambda: self._on_merge(tracker))

    def _on_part(self, tracker: ProgressTracker, index: int) -> None:
        tracker.start_part(index)
        self._report(tracker)

    def _on_step(self, tracker: ProgressTracker, label: str, index: int, count: int) -> None:
        tracker.start_step(index, count, label)
        self._report(tracker)

    def _on_merge(self, tracker: ProgressTracker) -> None:
        tracker.start_merge()
        self._report(tracker)

    def _on_fraction(self, tracker: ProgressTracker, fraction: float) -> None:
        tracker.set_fraction(fraction)
        self.progress.emit(tracker.overall, tracker.eta)

    def _report(self, tracker: ProgressTracker) -> None:
        label = (tracker.label, tracker.current_part, tracker.part_count)
        if label != self._last_label:
            self._last_label = label
            self.stage_changed.emit(tracker.label, tracker.current_part, tracker.part_count)
        if tracker.detail != self._last_detail:
            self._last_detail = tracker.detail
            self.detail_changed.emit(tracker.detail)
        self.progress.emit(tracker.overall, tracker.eta)

    def _summary(self, seconds: float) -> str:
        try:
            size = format_size(os.path.getsize(self._output))
        except OSError:
            size = "unknown"
        return (
            f"Output:    {self._output}\nDuration:  {format_time(self._duration)}\n"
            f"Size:      {size}\nTime:      {seconds:.1f}s"
        )
