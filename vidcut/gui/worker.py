from __future__ import annotations

import shutil
from typing import List

from PySide6.QtCore import QObject, Signal, Slot

from ..editor.export_pipeline import ExportPipeline


class CutWorker(QObject):
    """Runs an export pipeline on a separate thread."""

    stage = Signal(str, int, int)  # the phase, the part (1-based), the number of parts
    detail = Signal(str)
    progress = Signal(float, float)  # overall fraction 0..1, seconds left (-1 if unknown)
    finished = Signal(str, str)  # ("ok" | "fail" | "cancel", text)

    def __init__(self, pipeline: ExportPipeline, cleanup_dirs: List[str]) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._cleanup = cleanup_dirs
        self._result = ("fail", "The export stopped without a result.")

    def cancel(self) -> None:
        self._pipeline.request_cancel()

    @Slot()
    def run(self) -> None:
        p = self._pipeline
        p.stage_changed.connect(self.stage.emit)
        p.detail_changed.connect(self.detail.emit)
        p.progress.connect(self.progress.emit)
        p.succeeded.connect(lambda text: self._set("ok", text))
        p.failed.connect(lambda text: self._set("fail", text))
        p.cancelled.connect(lambda: self._set("cancel", "Cancelled."))
        try:
            p.run()
        except Exception as e:  # safety net
            self._set("fail", f"Unexpected error: {e}")
        finally:
            for folder in self._cleanup:
                shutil.rmtree(folder, ignore_errors=True)
        self.finished.emit(*self._result)

    def _set(self, kind: str, text: str) -> None:
        self._result = (kind, text)
