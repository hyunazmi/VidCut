"""The About tab: application and environment information."""

from __future__ import annotations

import platform
import re
import subprocess  # nosec B404
from typing import Callable

import PySide6
from PySide6.QtCore import Qt, qVersion
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QWidget

from .. import appinfo
from ..engine.ffmpeg_locator import FfmpegTools
from .layout_utils import centered_column

PAGE_WIDTH = 560


def _ffmpeg_version(ffmpeg: str) -> str:
    """The version number from `ffmpeg -version`, or '' if it cannot be read."""
    try:
        result = subprocess.run(  # nosec B603
            [ffmpeg, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    lines = result.stdout.splitlines()
    if not lines:
        return ""
    match = re.search(r"version\s+(\S+)", lines[0])
    return match.group(1) if match else lines[0]


def _selectable(label: QLabel) -> QLabel:
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


class AboutPage(QWidget):
    def __init__(self, locate_tools: Callable[[], FfmpegTools]) -> None:
        super().__init__()
        self._locate_tools = locate_tools
        self._ffmpeg_loaded = False

        title = QLabel(appinfo.NAME)
        font = QFont(title.font())
        font.setPointSize(font.pointSize() + 10)
        font.setWeight(QFont.Weight.DemiBold)
        title.setFont(font)

        description = QLabel(appinfo.DESCRIPTION)
        description.setObjectName("muted")
        description.setWordWrap(True)

        rule = QFrame()
        rule.setObjectName("rule")
        rule.setFrameShape(QFrame.Shape.HLine)

        homepage = QLabel(f'<a href="{appinfo.HOMEPAGE}">{appinfo.HOMEPAGE}</a>')
        homepage.setTextFormat(Qt.TextFormat.RichText)
        homepage.setOpenExternalLinks(True)

        self._ffmpeg_version_value = QLabel("Checking...")
        self._ffmpeg_path_value = _selectable(QLabel(""))
        qt_text = f"Qt {qVersion()}, PySide6 {getattr(PySide6, '__version__', '?')}"
        rows = [
            ("Version", QLabel(appinfo.VERSION)),
            ("Author", QLabel(appinfo.AUTHOR)),
            ("License", QLabel(appinfo.LICENSE)),
            ("Homepage", homepage),
            ("FFmpeg", self._ffmpeg_version_value),
            ("FFmpeg path", self._ffmpeg_path_value),
            ("Interface", QLabel(qt_text)),
            ("Python", QLabel(platform.python_version())),
        ]
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)
        grid.setColumnMinimumWidth(0, 100)
        grid.setColumnStretch(1, 1)
        for row, (name, value) in enumerate(rows):
            key = QLabel(name)
            key.setObjectName("muted")
            grid.addWidget(key, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value, row, 1, Qt.AlignmentFlag.AlignTop)

        column = centered_column(self, PAGE_WIDTH, margins=(24, 48, 24, 24))
        column.setSpacing(14)
        column.addWidget(title)
        column.addWidget(description)
        column.addSpacing(6)
        column.addWidget(rule)
        column.addSpacing(6)
        column.addLayout(grid)
        column.addStretch(1)

    def invalidate(self) -> None:
        """Forget the cached FFmpeg details (the location changed)."""
        self._ffmpeg_loaded = False
        self._ffmpeg_version_value.setText("Checking...")
        self._ffmpeg_path_value.setText("")

    def refresh(self) -> None:
        """Resolve the FFmpeg details the first time the tab is shown."""
        if self._ffmpeg_loaded:
            return
        self._ffmpeg_loaded = True
        tools = self._locate_tools()
        if not tools.is_valid():
            self._ffmpeg_version_value.setText("Not found")
            self._ffmpeg_path_value.setText("Install FFmpeg, or set its folder in the Settings tab.")
            return
        self._ffmpeg_version_value.setText(_ffmpeg_version(tools.ffmpeg) or "Unknown")
        self._ffmpeg_path_value.setText(tools.ffmpeg)
