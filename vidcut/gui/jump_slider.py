"""A slider whose handle jumps straight to the place that is clicked."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSlider, QStyle

HANDLE_WIDTH = 12  # keep in step with QSlider::handle in theme.py


class JumpSlider(QSlider):
    def __init__(self, minimum: int = 0, maximum: int = 100) -> None:
        super().__init__(Qt.Orientation.Horizontal)
        self.setRange(minimum, maximum)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def value_at(self, x: float) -> int:
        """The value that belongs to horizontal position x inside the slider."""
        span = max(1, self.width() - HANDLE_WIDTH)
        return QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), int(x - HANDLE_WIDTH / 2), span)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setValue(self.value_at(event.position().x()))  # jump first, then drag as usual
        super().mousePressEvent(event)
