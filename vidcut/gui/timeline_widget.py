"""Paints the timeline: a ruler and the clips of the video, in one row.

A press or a drag on the timeline moves the playhead. Clips are cut and deleted with the keyboard or the
right-click menu; the timeline itself does not move clips around.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from ..core.time_utils import format_time
from ..editor.timeline import TimelineModel
from . import theme

MARGIN = 12
RULER_H = 22
TRACK_TOP = 28
TRACK_H = 56
BOTTOM_PAD = 10
TICK_STEPS = (0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800, 3600)

C_BG = QColor(theme.PANEL)
C_RULER = QColor(theme.BG)
C_TICK = QColor("#4a4d54")
C_LABEL = QColor(theme.MUTED)
C_CLIP = QColor("#34527d")
C_CLIP_CURRENT = QColor("#4574b5")
C_CLIP_TEXT = QColor("#e8eefa")
C_PLAYHEAD = QColor(theme.PLAYHEAD)
C_OUTLINE = QColor(theme.ACCENT)
CLIP_GAP_PX = 2


def timeline_height() -> int:
    return TRACK_TOP + TRACK_H + BOTTOM_PAD


def _short(seconds: float) -> str:
    text = format_time(seconds)  # HH:MM:SS.mmm
    return text[:-4] if seconds >= 1 else text[3:]


class TimelineWidget(QWidget):
    seek_requested = Signal(float)  # timeline seconds
    zoom_requested = Signal(float)  # zoom factor
    pan_requested = Signal(int)  # horizontal scroll in pixels
    context_menu_requested = Signal(QPoint, float)  # screen position, timeline seconds

    def __init__(self, model: TimelineModel, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        self.pps = 80.0  # pixels per second
        self.playhead = 0.0
        self._scrubbing = False
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)  # clicking here takes focus away from text fields
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(timeline_height())
        model.on_change(self.refresh)

    # ---- geometry ---------------------------------------------------
    def x_of(self, t: float) -> int:
        return int(MARGIN + t * self.pps)

    def t_of(self, x: float) -> float:
        return max(0.0, (x - MARGIN) / self.pps)

    def refresh(self) -> None:
        self.setMinimumWidth(int(self.model.total * self.pps) + 2 * MARGIN)
        self.update()

    def set_pps(self, pps: float) -> None:
        self.pps = min(max(pps, 0.5), 4000.0)
        self.refresh()

    def fit(self, viewport_width: int) -> None:
        total = self.model.total
        if total > 0:
            self.set_pps(max(1.0, (viewport_width - 2 * MARGIN) / total))

    def set_playhead(self, t: float) -> None:
        self.playhead = max(0.0, t)
        self.update()

    # ---- painting ---------------------------------------------------
    def _tick_step(self) -> float:
        for step in TICK_STEPS:
            if step * self.pps >= 80:
                return step
        return TICK_STEPS[-1]

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), C_BG)
        font = QFont(self.font())
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1.5))
        p.setFont(font)
        self._paint_ruler(p)
        self._paint_clips(p)
        self._paint_playhead(p)

    def _paint_ruler(self, p: QPainter) -> None:
        p.fillRect(0, 0, self.width(), RULER_H, C_RULER)
        step = self._tick_step()
        last = int(max(self.model.total, self.t_of(self.width())) / step) + 1
        for i in range(last + 1):
            x = self.x_of(i * step)
            p.setPen(QPen(C_TICK))
            p.drawLine(x, RULER_H - 6, x, RULER_H)
            p.setPen(QPen(C_LABEL))
            p.drawText(x + 4, RULER_H - 8, _short(i * step))
        p.setPen(QPen(C_TICK))
        p.drawLine(0, RULER_H, self.width(), RULER_H)

    def _paint_clips(self, p: QPainter) -> None:
        clips = self.model.clips
        if not clips:
            message = "Nothing left on the timeline. Press Ctrl+Z to undo." if self.model.source else "No video loaded."
            p.setPen(QPen(C_LABEL))
            p.drawText(QRectF(0, TRACK_TOP, self.width(), TRACK_H), Qt.AlignmentFlag.AlignCenter, message)
            return
        current = self.model.index_at(self.playhead)
        metrics = QFontMetrics(p.font())
        name = os.path.basename(self.model.source.path) if self.model.source else ""
        for i, (clip, off) in enumerate(zip(clips, self.model.offsets())):
            x0 = self.x_of(off)
            x1 = self.x_of(off + clip.length)
            rect = QRectF(x0 + CLIP_GAP_PX / 2, TRACK_TOP, max(1.0, x1 - x0 - CLIP_GAP_PX), TRACK_H)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(C_CLIP_CURRENT if i == current else C_CLIP)
            p.drawRoundedRect(rect, 2, 2)
            if i == current:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(C_OUTLINE, 1.5))
                p.drawRoundedRect(rect.adjusted(0.75, 0.75, -0.75, -0.75), 2, 2)
            if rect.width() > 64:
                self._label_clip(p, metrics, rect, name, _short(clip.length))

    @staticmethod
    def _label_clip(p: QPainter, metrics: QFontMetrics, rect: QRectF, name: str, length: str) -> None:
        inner = rect.adjusted(8, 5, -8, -5)
        p.setPen(QPen(C_CLIP_TEXT))
        p.drawText(
            inner,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, int(inner.width())),
        )
        p.drawText(inner, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, length)

    def _paint_playhead(self, p: QPainter) -> None:
        px = self.x_of(self.playhead)
        p.setPen(QPen(C_PLAYHEAD, 1))
        p.drawLine(px, 0, px, self.height())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(C_PLAYHEAD)
        p.drawPolygon(
            QPolygonF(
                [QPointF(px - 5, 0), QPointF(px + 6, 0), QPointF(px + 6, 8), QPointF(px + 0.5, 13), QPointF(px - 5, 8)]
            )
        )

    # ---- mouse and wheel --------------------------------------------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._scrubbing = True
            self.seek_requested.emit(min(self.t_of(event.position().x()), self.model.total))

    def mouseMoveEvent(self, event) -> None:
        if self._scrubbing:
            self.seek_requested.emit(min(self.t_of(event.position().x()), self.model.total))

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._scrubbing = False

    def contextMenuEvent(self, event) -> None:
        seconds = min(self.t_of(event.pos().x()), self.model.total)
        self.context_menu_requested.emit(event.globalPos(), seconds)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_requested.emit(1.25 if delta > 0 else 0.8)
        else:
            self.pan_requested.emit(-delta)
        event.accept()
