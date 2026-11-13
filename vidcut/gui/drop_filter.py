"""Lets a whole window accept dropped video files."""

from __future__ import annotations

from typing import List

from PySide6.QtCore import QEvent, QObject, QTimer, Signal
from PySide6.QtWidgets import QLineEdit, QWidget

from ..core.formats import is_video_file


def video_paths(mime) -> List[str]:
    """Local video files in a drag-and-drop payload (a QMimeData)."""
    return [url.toLocalFile() for url in mime.urls() if url.isLocalFile() and is_video_file(url.toLocalFile())]


class VideoDropFilter(QObject):
    videos_dropped = Signal(list)  # the paths of the videos that were dropped, in order
    hover_changed = Signal(bool)  # True while a video is held over the window
    rejected = Signal()  # something that is not a video was dropped

    def attach(self, root: QWidget) -> None:
        """Accept drops on `root` and on every widget inside it."""
        for widget in [root, *root.findChildren(QWidget)]:
            widget.setAcceptDrops(True)
            widget.installEventFilter(self)
        # Text fields would otherwise swallow the drop and paste the file path into themselves.
        for edit in root.findChildren(QLineEdit):
            edit.setAcceptDrops(False)

    def eventFilter(self, obj, event) -> bool:
        kind = event.type()
        if kind in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            if video_paths(event.mimeData()):
                event.acceptProposedAction()
                self.hover_changed.emit(True)
            else:
                event.ignore()
            return True
        if kind == QEvent.Type.DragLeave:
            self.hover_changed.emit(False)
            return True
        if kind == QEvent.Type.Drop:
            self.hover_changed.emit(False)
            paths = video_paths(event.mimeData())
            if paths:
                event.acceptProposedAction()
                # Handle it after the drop has finished, so a dialog never blocks the file manager.
                QTimer.singleShot(0, lambda dropped=paths: self.videos_dropped.emit(dropped))
            else:
                event.ignore()
                self.rejected.emit()
            return True
        return super().eventFilter(obj, event)
