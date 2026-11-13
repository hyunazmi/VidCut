"""Turns the SVG icons of icon_svgs into QIcon objects, in the colors of the theme."""

from __future__ import annotations

from functools import cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import theme
from .icon_svgs import svg_document

LOGICAL_SIZE = 24  # the grid size of the icons
RENDER_SCALE = 2  # drawn at twice the size so they stay sharp on high resolution screens


def _pixmap(name: str, color: str) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg_document(name, color).encode("utf-8")))
    pixmap = QPixmap(LOGICAL_SIZE * RENDER_SCALE, LOGICAL_SIZE * RENDER_SCALE)
    pixmap.setDevicePixelRatio(RENDER_SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, LOGICAL_SIZE, LOGICAL_SIZE))
    painter.end()
    return pixmap


@cache
def icon(name: str, color: str = theme.TEXT) -> QIcon:
    """The icon in the given color, with a dimmed version for disabled buttons."""
    result = QIcon()
    result.addPixmap(_pixmap(name, color), QIcon.Mode.Normal)
    result.addPixmap(_pixmap(name, theme.DISABLED), QIcon.Mode.Disabled)
    return result
