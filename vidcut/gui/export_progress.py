"""The export popup: a window of its own that shows the progress of an export and how it ended.

It is opened when the export starts and stays open until the user closes it, so the result can be read
and the folder can be opened. While the export runs it is application-modal, so the editor is locked.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from ..core.time_utils import format_eta
from . import icons

BAR_STEPS = 1000  # the bar works in tenths of a percent
MAX_ERROR_CHARS = 300  # a failed export shows a short reason, never a full log


class ExportProgress(QDialog):
    cancel_requested = Signal()
    show_folder_requested = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export")
        self.setModal(True)
        self.setMinimumWidth(460)
        self._running = False
        self._cancelling = False

        self.title = QLabel()
        font = QFont(self.title.font())
        font.setPointSize(font.pointSize() + 2)
        font.setWeight(QFont.Weight.DemiBold)
        self.title.setFont(font)
        self.title.setWordWrap(True)

        self.bar = QProgressBar()
        self.bar.setRange(0, BAR_STEPS)
        self.bar.setFormat("%p%")
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        # The part counter, for example "1 / 1" or "2 / 3", next to the bar.
        self.counter = QLabel("")
        self.counter.setObjectName("muted")
        self.counter.setMinimumWidth(56)
        self.counter.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        bar_row = QHBoxLayout()
        bar_row.setSpacing(12)
        bar_row.addWidget(self.bar, 1)
        bar_row.addWidget(self.counter)

        self.percent = QLabel("")
        self.percent.setObjectName("muted")
        self.detail = QLabel("")  # what the current step does, or the reason for a failure
        self.detail.setObjectName("muted")
        self.detail.setWordWrap(True)
        self.eta = QLabel("")
        self.eta.setObjectName("muted")

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setIcon(icons.icon("close"))
        self.cancel_button.clicked.connect(self._cancel)
        self.folder_button = QPushButton("Show folder")
        self.folder_button.setIcon(icons.icon("folder"))
        self.folder_button.clicked.connect(self.show_folder_requested)
        self.done_button = QPushButton("Close")
        self.done_button.clicked.connect(lambda: self.reject())
        for button in (self.cancel_button, self.folder_button, self.done_button):
            button.setAutoDefault(False)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        for button in (self.cancel_button, self.folder_button, self.done_button):
            buttons.addWidget(button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addSpacing(4)
        layout.addLayout(bar_row)
        layout.addWidget(self.percent)
        layout.addWidget(self.detail)
        layout.addWidget(self.eta)
        layout.addSpacing(10)
        layout.addLayout(buttons)

    # ---- states -----------------------------------------------------
    def start(self) -> None:
        """Back to the running state, before any progress is known."""
        self._running = True
        self._cancelling = False
        self.title.setText("Preparing the export")
        self.bar.setValue(0)
        self.bar.show()
        self.counter.setText("")
        self.percent.setText("")
        self.detail.setText("")
        self.eta.setText("")
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.folder_button.hide()
        self.done_button.hide()

    def set_stage(self, text: str, part: int, count: int) -> None:
        if not self._cancelling:
            self.title.setText(text)
            self.counter.setText(f"{part} / {count}")

    def set_detail(self, text: str) -> None:
        if not self._cancelling:
            self.detail.setText(text)

    def set_progress(self, fraction: float, eta: float) -> None:
        if self._cancelling:
            return
        fraction = min(max(fraction, 0.0), 1.0)
        self.bar.setValue(int(round(fraction * BAR_STEPS)))
        self.percent.setText(f"{round(fraction * 100)}%")
        self.eta.setText(f"{format_eta(eta)} left" if eta >= 0 else "")

    def show_result(self, kind: str, text: str = "") -> None:
        """How the export ended: kind is "ok", "fail" or "cancel". A cancelled export closes the popup."""
        self._running = False
        self._cancelling = False
        self.eta.setText("")
        self.cancel_button.hide()
        if kind == "cancel":
            self.close()
            return
        self.done_button.show()
        if kind == "ok":
            self.title.setText("Export finished")
            self.bar.setValue(BAR_STEPS)
            self.percent.setText("100%")
            self.detail.setText("")
            self.folder_button.show()
        else:
            self.title.setText("Export failed")
            self.bar.hide()
            self.percent.setText("")
            self.detail.setText(_short_reason(text))

    # ---- closing ----------------------------------------------------
    def _cancel(self) -> None:
        self._cancelling = True
        self.cancel_button.setEnabled(False)
        self.title.setText("Cancelling")
        self.detail.setText("")
        self.eta.setText("")
        self.cancel_requested.emit()

    def reject(self) -> None:
        """Closing the window while the export runs cancels it, the same as the Cancel button."""
        if self._running:
            if not self._cancelling:
                self._cancel()
            return
        super().reject()


def _short_reason(text: str) -> str:
    """The last meaningful line of an error text, cut to a length that fits the popup."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    reason = lines[-1] if lines else ""
    return reason if len(reason) <= MAX_ERROR_CHARS else reason[: MAX_ERROR_CHARS - 3] + "..."
