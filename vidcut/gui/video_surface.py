"""The picture of the preview: paints the RGB frames that PreviewController gets from ffmpeg."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QWidget

from ..engine.preview_media import Frame

BACKGROUND = QColor("#000000")


class VideoSurface(QWidget):
    """A black area that shows one picture, as large as fits and with the right shape."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._image: Optional[QImage] = None
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    def show_frame(self, frame: Frame) -> None:
        # The image is copied: QImage does not keep the bytes it was made from.
        self._image = QImage(frame.data, frame.width, frame.height, frame.width * 3, QImage.Format.Format_RGB888).copy()
        self.update()

    def clear(self) -> None:
        self._image = None
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), BACKGROUND)
        image = self._image
        if image is None or image.isNull() or self.width() <= 0 or self.height() <= 0:
            return
        scale = min(self.width() / image.width(), self.height() / image.height())
        width, height = max(1, int(image.width() * scale)), max(1, int(image.height() * scale))
        target = QRect((self.width() - width) // 2, (self.height() - height) // 2, width, height)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(target, image)
