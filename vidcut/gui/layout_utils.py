"""Layout helpers shared by the pages."""

from __future__ import annotations

from typing import Tuple

from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget


def centered_column(
    page: QWidget, max_width: int, margins: Tuple[int, int, int, int] = (24, 32, 24, 24)
) -> QVBoxLayout:
    """Lay `page` out as one horizontally centered column and return the column's layout.

    Add your widgets to the returned layout, then finish with `addStretch(1)` so the content
    stays at the top.

    Do not build this as a fixed-width widget with AlignHCenter. A layout asks such a widget
    for its height using the full page width, not the fixed width. Word-wrapped labels then
    wrap into fewer lines than they really need, the column gets too little height, and the
    rows at the bottom are squeezed and cut off. Here the column is an ordinary expanding
    widget with a maximum width, so the layout works out its height at the right width.
    """
    column = QWidget()
    column.setMaximumWidth(max_width)
    column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    inner = QVBoxLayout(column)
    inner.setContentsMargins(0, 0, 0, 0)

    outer = QHBoxLayout(page)
    outer.setContentsMargins(*margins)
    outer.addStretch(1)
    outer.addWidget(column, 100)
    outer.addStretch(1)
    return inner
