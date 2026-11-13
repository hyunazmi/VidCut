"""The Settings tab: the FFmpeg location and the export quality."""

from __future__ import annotations

import os
from typing import Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QWidget,
)

from ..core.encode_settings import AUDIO_BITRATE_CHOICES, CRF_MAX, CRF_MIN, PRESETS, EncodeSettings
from ..engine import ffmpeg_locator
from . import icons, settings
from .layout_utils import centered_column

PAGE_WIDTH = 560  # the same column width as the About tab


def _title(text: str, grow: int) -> QLabel:
    """The same title and section headings as the About tab."""
    label = QLabel(text)
    font = QFont(label.font())
    font.setPointSize(font.pointSize() + grow)
    font.setWeight(QFont.Weight.DemiBold)
    label.setFont(font)
    return label


def _heading(text: str) -> QLabel:
    return _title(text, 2)


def _muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    return label


def _value_label() -> QLabel:
    label = QLabel("")
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


class SettingsPanel(QScrollArea):
    """The Settings tab. It is a page like About: flat, one centered column, no frame."""

    ffmpeg_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("page")
        self.setWidgetResizable(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.viewport().setStyleSheet("background: transparent;")

        # ---- FFmpeg ----
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Automatic (search the system PATH)")
        self.edit.setFocusPolicy(Qt.FocusPolicy.ClickFocus)  # not focused at start-up
        self.edit.editingFinished.connect(self._apply)
        browse = QPushButton("Browse")
        browse.setIcon(icons.icon("folder"))
        browse.setAutoDefault(False)
        browse.clicked.connect(self._browse)
        automatic = QPushButton("Use automatic")
        automatic.setAutoDefault(False)
        automatic.clicked.connect(self._reset)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(browse)
        buttons.addWidget(automatic)
        buttons.addStretch(1)

        self.error = QLabel("")
        self.error.setObjectName("error")
        self.error.setWordWrap(True)
        self.error.hide()

        self.ffmpeg_value = _value_label()
        self.ffprobe_value = _value_label()
        detected = QGridLayout()
        detected.setHorizontalSpacing(16)
        detected.setVerticalSpacing(6)
        detected.setColumnMinimumWidth(0, 60)
        detected.setColumnStretch(1, 1)
        for index, (name, value) in enumerate((("ffmpeg", self.ffmpeg_value), ("ffprobe", self.ffprobe_value))):
            key = QLabel(name)
            key.setObjectName("muted")
            detected.addWidget(key, index, 0, Qt.AlignmentFlag.AlignTop)
            detected.addWidget(value, index, 1, Qt.AlignmentFlag.AlignTop)

        # ---- export quality ----
        self.preset = QComboBox()
        self.preset.addItems(PRESETS)
        self.crf = QSpinBox()
        self.crf.setRange(CRF_MIN, CRF_MAX)
        self.audio_bitrate = QComboBox()
        self.audio_bitrate.addItems(AUDIO_BITRATE_CHOICES)
        for combo in (self.preset, self.audio_bitrate):
            combo.currentTextChanged.connect(self._save_quality)
        self.crf.valueChanged.connect(self._save_quality)
        reset_quality = QPushButton("Reset to defaults")
        reset_quality.setAutoDefault(False)
        reset_quality.clicked.connect(self._reset_quality)

        quality = QGridLayout()
        quality.setHorizontalSpacing(16)
        quality.setVerticalSpacing(8)
        quality.setColumnMinimumWidth(0, 96)
        quality.setColumnStretch(1, 1)
        controls: Tuple[Tuple[str, QWidget], ...] = (
            ("x264 preset", self.preset),
            ("CRF", self.crf),
            ("Audio bitrate", self.audio_bitrate),
        )
        for index, (name, control) in enumerate(controls):
            label = QLabel(name)
            label.setObjectName("muted")
            quality.addWidget(label, index, 0)
            quality.addWidget(control, index, 1)

        content = QWidget()
        column = centered_column(content, PAGE_WIDTH, margins=(24, 48, 24, 24))
        column.setSpacing(12)
        column.addWidget(_title("Settings", 10))
        column.addWidget(_muted("Tools and export quality for VidCut."))
        rule = QFrame()
        rule.setObjectName("rule")
        rule.setFrameShape(QFrame.Shape.HLine)
        column.addSpacing(6)
        column.addWidget(rule)
        column.addSpacing(6)
        column.addWidget(_heading("FFmpeg"))
        column.addWidget(
            _muted(
                "VidCut uses the ffmpeg and ffprobe installed on this computer. Choose the folder "
                "that contains both, or leave it empty to search the system PATH."
            )
        )
        column.addWidget(self.edit)
        column.addLayout(buttons)
        column.addWidget(self.error)
        column.addSpacing(2)
        column.addLayout(detected)
        column.addSpacing(18)
        column.addWidget(_heading("Export quality"))
        column.addWidget(_muted("Used by every export. A lower CRF means better quality and a larger file."))
        column.addLayout(quality)
        column.addWidget(reset_quality, 0, Qt.AlignmentFlag.AlignLeft)
        column.addStretch(1)
        self.setWidget(content)

        self.refresh()

    # ---- state ------------------------------------------------------
    def refresh(self) -> None:
        """Show the saved folder and what VidCut detects right now."""
        self.edit.setText(settings.saved_ffmpeg_dir())
        self.error.hide()
        tools = settings.locate_tools()
        self.ffmpeg_value.setText(tools.ffmpeg or "Not found")
        self.ffprobe_value.setText(tools.ffprobe or "Not found")
        self._show_quality(settings.load_encode_settings())

    def _show_quality(self, encode: EncodeSettings) -> None:
        """Fill the quality controls without treating it as a change made by the user."""
        for control, show in (
            (self.preset, lambda: self.preset.setCurrentText(encode.preset)),
            (self.crf, lambda: self.crf.setValue(encode.crf)),
            (self.audio_bitrate, lambda: self.audio_bitrate.setCurrentText(encode.audio_bitrate)),
        ):
            control.blockSignals(True)
            show()
            control.blockSignals(False)

    def _show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.show()

    # ---- actions ----------------------------------------------------
    def _apply(self) -> None:
        text = self.edit.text().strip()
        if text == settings.saved_ffmpeg_dir():
            return
        if not text:
            self._save("")
            return
        directory = ffmpeg_locator.resolve_tools_dir(text)
        if not os.path.isdir(directory):
            self._show_error(f"This folder does not exist: {directory}")
            return
        missing = ffmpeg_locator.missing_tools(directory)
        if missing:
            self._show_error(f"Not found in this folder: {', '.join(missing)}.")
            return
        self._save(directory)

    def _save(self, directory: str) -> None:
        settings.save_ffmpeg_dir(directory)
        self.refresh()
        self.ffmpeg_changed.emit()

    def _browse(self) -> None:
        start = settings.saved_ffmpeg_dir() or os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Select the folder that contains ffmpeg and ffprobe", start)
        if directory:
            self.edit.setText(directory)
            self._apply()

    def _reset(self) -> None:
        self.edit.setText("")
        self._apply()

    # ---- export quality ---------------------------------------------
    def _save_quality(self, *_args) -> None:
        """Every change is saved at once, so the next export already uses it."""
        settings.save_encode_settings(
            EncodeSettings(
                preset=self.preset.currentText(), crf=self.crf.value(), audio_bitrate=self.audio_bitrate.currentText()
            )
        )

    def _reset_quality(self) -> None:
        defaults = EncodeSettings()
        self._show_quality(defaults)
        settings.save_encode_settings(defaults)
