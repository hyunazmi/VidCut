"""The export workflow: ask for the file name, run the pipeline on a worker thread, and show it in a popup.

The popup (ExportProgress) is opened when the export starts. It shows the progress and, at the end, the result.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from PySide6.QtCore import QObject, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from ..core.formats import default_output_extension
from ..editor.export_plan import ExportPlan, ExportPlanError, ExportRequest, default_output_path
from ..engine.ffmpeg_locator import FfmpegTools
from . import settings
from .dialogs import ExportDialog
from .export_progress import ExportProgress
from .worker import CutWorker


class ExportController(QObject):
    started = Signal()
    finished = Signal(str, str)  # kind ("ok" | "fail" | "cancel"), text for the user
    closed = Signal(str)  # the popup was closed: the kind of the result

    def __init__(self, window: QWidget, locate_tools: Callable[[], FfmpegTools]) -> None:
        super().__init__(window)
        self._window = window
        self._locate_tools = locate_tools
        self._thread: Optional[QThread] = None
        self._worker: Optional[CutWorker] = None
        self._popup: Optional[ExportProgress] = None
        self._kind = ""
        self.last_output = ""

    @property
    def busy(self) -> bool:
        return self._thread is not None

    def start(self, request: Optional[ExportRequest]) -> None:
        if self.busy or request is None or not request.clips:
            return
        tools = self._locate_tools()
        if not tools.is_valid():
            QMessageBox.warning(
                self._window,
                "Export",
                "ffmpeg / ffprobe was not found.\nInstall FFmpeg, or set the folder "
                "that contains both in the Settings tab.",
            )
            return

        default_path = default_output_path(request.source, default_output_extension(request.source))
        dialog = ExportDialog(self._window, default_path)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            plan = request.build(dialog.output_path(), tools.ffmpeg, tools.ffprobe, settings.load_encode_settings())
        except ExportPlanError as e:
            QMessageBox.warning(self._window, "Export", str(e))
            return
        self._run(plan, dialog.output_path())

    def cancel(self) -> None:
        """Ask the running export to stop. Safe to call from the GUI thread at any time."""
        if self._worker is not None:
            self._worker.cancel()

    def show_folder(self) -> None:
        if self.last_output:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self.last_output)))

    def shutdown(self) -> None:
        """Called when the window closes: cancel a running export and wait for the thread."""
        self.cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)

    # ---- internals --------------------------------------------------
    def _run(self, plan: ExportPlan, output: str) -> None:
        self.last_output = output
        self._kind = ""
        self._thread = QThread(self)
        self._worker = CutWorker(plan.pipeline, plan.cleanup_dirs)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)

        popup = ExportProgress(self._window)
        self._popup = popup
        popup.cancel_requested.connect(self.cancel)
        popup.show_folder_requested.connect(self.show_folder)
        popup.finished.connect(self._on_popup_closed)
        popup.start()

        self._worker.stage.connect(popup.set_stage)
        self._worker.detail.connect(popup.set_detail)
        self._worker.progress.connect(popup.set_progress)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()
        popup.show()  # application-modal (set in the popup): the editor is locked
        self.started.emit()

    def _on_finished(self, kind: str, text: str) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(5000)
            self._thread.deleteLater()
        self._thread = None
        self._worker = None
        self._kind = kind
        if self._popup is not None:
            self._popup.show_result(kind, text)  # a cancelled export closes the popup by itself
        self.finished.emit(kind, text)

    def _on_popup_closed(self, _result: int) -> None:
        self._popup = None
        self.closed.emit(self._kind)
