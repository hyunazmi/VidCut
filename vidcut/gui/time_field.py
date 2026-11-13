"""A small form field: type a time, press Enter, and the playhead goes there."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QLineEdit

from ..core.time_utils import format_time
from ..editor.timecode import parse_time
from . import icons

FIELD_WIDTH = 160


class TimeField(QLineEdit):
    """Shows the playhead time and lets the user type another one.

    While the field has focus the user is typing, so the playhead does not overwrite the text.
    Enter jumps and leaves the field; Escape or clicking elsewhere throws the typing away.
    """

    time_entered = Signal(float)  # seconds, when the text was a valid time
    rejected = Signal(str)  # the text, when it was not a time

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("timefield")
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setFixedWidth(FIELD_WIDTH)
        self.addAction(icons.icon("clock"), QLineEdit.ActionPosition.LeadingPosition)
        self.setToolTip("Go to time (Ctrl+G). Type a time such as 90, 1:30 or 00:01:30.500, then press Enter.")
        self._seconds = 0.0
        self.setText(format_time(0.0))
        self.returnPressed.connect(self._commit)

    def show_seconds(self, seconds: float) -> None:
        """Follow the playhead (unless the user is typing)."""
        self._seconds = seconds
        if not self.hasFocus():
            self.setText(format_time(seconds))

    def _restore(self) -> None:
        self.setText(format_time(self._seconds))

    def _commit(self) -> None:
        value = parse_time(self.text())
        if value is None:
            self.rejected.emit(self.text())
            self._restore()
            QTimer.singleShot(0, self.selectAll)  # keep the focus so the user can try again
            return
        self.time_entered.emit(value)
        self.clearFocus()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._restore()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self._restore()
            self.clearFocus()
            return
        super().keyPressEvent(event)
