"""The scrollable, zoomable timeline: a TimelineWidget inside a scroll area."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtWidgets import QScrollArea

from ..editor.timeline import TimelineModel
from .timeline_widget import TimelineWidget, timeline_height

SCROLLBAR_ROOM = 16  # extra height so the horizontal scroll bar never covers the track
ZOOM_STEP = 1.25


class TimelineView(QScrollArea):
    seek_requested = Signal(float)  # timeline seconds
    context_menu_requested = Signal(QPoint, float)  # screen position, timeline seconds

    def __init__(self, model: TimelineModel) -> None:
        super().__init__()
        self._fit_mode = True
        self.timeline = TimelineWidget(model)
        self.timeline.seek_requested.connect(self.seek_requested)
        self.timeline.context_menu_requested.connect(self.context_menu_requested)
        self.timeline.zoom_requested.connect(self.zoom)
        self.timeline.pan_requested.connect(self.pan)

        self.setWidgetResizable(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.timeline)
        self.setFixedHeight(timeline_height() + SCROLLBAR_ROOM)
        self._apply_scrollbar_policy()

    # ---- view state -------------------------------------------------
    def fit(self) -> None:
        """Show the whole timeline. It keeps fitting when the window is resized."""
        self._fit_mode = True
        self._apply_scrollbar_policy()
        self.timeline.fit(self.viewport().width())

    def zoom(self, factor: float) -> None:
        """Zoom around the playhead."""
        self._fit_mode = False
        self._apply_scrollbar_policy()
        bar = self.horizontalScrollBar()
        playhead = self.timeline.playhead
        offset = self.timeline.x_of(playhead) - bar.value()
        self.timeline.set_pps(self.timeline.pps * factor)
        # The scroll range only grows once the layout has run, so move the bar afterwards.
        QTimer.singleShot(0, lambda: bar.setValue(self.timeline.x_of(playhead) - offset))

    def zoom_in(self) -> None:
        self.zoom(ZOOM_STEP)

    def zoom_out(self) -> None:
        self.zoom(1.0 / ZOOM_STEP)

    def pan(self, pixels: int) -> None:
        bar = self.horizontalScrollBar()
        bar.setValue(bar.value() + pixels)

    def set_playhead(self, seconds: float) -> None:
        self.timeline.set_playhead(seconds)
        self.ensureVisible(self.timeline.x_of(seconds), 0, 80, 0)

    def _apply_scrollbar_policy(self) -> None:
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff if self._fit_mode else Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit_mode:
            self.timeline.fit(self.viewport().width())
