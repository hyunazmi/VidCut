"""The Editor tab: the preview, the transport controls and the timeline."""

from __future__ import annotations

import os
from typing import Callable, Dict, Optional

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core.media_info import MediaInfo
from ..core.time_utils import format_time
from ..editor.export_plan import ExportRequest
from ..editor.timeline import TimelineModel
from ..engine import media_probe
from ..engine.errors import CancelToken, CutError
from ..engine.ffmpeg_locator import FfmpegTools
from ..engine.process_runner import ProcessRunner
from . import icons
from .jump_slider import JumpSlider
from .playback import DEFAULT_VOLUME, PlaybackController
from .shortcuts import FAR_STEP_FRAMES, JUMP_SECONDS
from .time_field import TimeField
from .timeline_view import TimelineView
from .video_surface import VideoSurface


class EditorPage(QWidget):
    message = Signal(str, int)  # status bar text, timeout in milliseconds
    state_changed = Signal()  # clips, undo or redo availability changed
    video_opened = Signal(str)  # path of the video that was just opened

    def __init__(self, locate_tools: Callable[[], FfmpegTools]) -> None:
        super().__init__()
        self._locate_tools = locate_tools
        self.model = TimelineModel()
        self._media: Dict[str, MediaInfo] = {}  # what ffprobe said about the video of the project
        self._playhead = 0.0  # seconds on the timeline
        self._probe_error = ""  # why the last probe failed
        self._sound_warned = False

        self._build_ui()
        self.playback = PlaybackController(self.model, self.video, self._ffmpeg_path, self._media_info, self)
        self.playback.position_changed.connect(self._set_playhead)
        self.playback.playing_changed.connect(self._on_playing_changed)
        self.playback.error.connect(lambda text: self.message.emit(f"Player error: {text}", 8000))
        self._on_volume_changed(self.volume_slider.value())
        self.model.on_change(self._on_model_changed)
        self._refresh_time_widgets()

    # ================= construction =================
    def _build_ui(self) -> None:
        self.video = VideoSurface()
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.video.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.video.customContextMenuRequested.connect(
            lambda pos: self._show_context_menu(self.video.mapToGlobal(pos), self._playhead)
        )

        # The drop zone is shown until a video is loaded.
        self.placeholder = QLabel("Drop a video here\nor press Ctrl+O to open one")
        self.placeholder.setObjectName("dropzone")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stage = QStackedWidget()
        self.stage.addWidget(self.placeholder)
        self.stage.addWidget(self.video)
        self.stage.setCurrentWidget(self.placeholder)

        self.play_button = self._icon_button("play", "Play / Pause (Space)", "transport")
        self.play_button.setFixedSize(40, 32)
        self.play_button.clicked.connect(self.toggle_play)

        self.time_field = TimeField()
        self.time_field.setFocusPolicy(Qt.FocusPolicy.ClickFocus)  # not focused at start-up: Ctrl+G or a click
        self.time_field.time_entered.connect(self.go_to_time)
        self.time_field.rejected.connect(
            lambda _text: self.message.emit("That is not a time. Try 90, 1:30 or 00:01:30.500.", 5000)
        )
        self.total_label = QLabel()
        self.total_label.setObjectName("muted")
        self.total_label.setFont(self.time_field.font())

        self.mute_button = self._icon_button("volume", "Mute the preview")
        self.mute_button.setCheckable(True)
        self.mute_button.toggled.connect(self._on_master_muted)
        self.volume_slider = JumpSlider(0, 100)
        self.volume_slider.setValue(int(DEFAULT_VOLUME * 100))
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.volume_label = QLabel()
        self.volume_label.setObjectName("muted")
        self.volume_label.setFixedWidth(40)
        self.volume_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        transport = QHBoxLayout()
        transport.setContentsMargins(0, 0, 0, 0)
        transport.setSpacing(12)
        transport.addWidget(self.play_button)
        transport.addWidget(self.time_field)
        transport.addWidget(self.total_label)
        transport.addStretch(1)
        transport.addWidget(self.mute_button)
        transport.addWidget(self.volume_slider)
        transport.addWidget(self.volume_label)
        self.transport_bar = QWidget()
        self.transport_bar.setLayout(transport)

        self.timeline = TimelineView(self.model)
        self.timeline.seek_requested.connect(self.seek_timeline)
        self.timeline.context_menu_requested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.stage, 1)
        layout.addWidget(self.transport_bar)
        layout.addWidget(self.timeline)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    @staticmethod
    def _icon_button(icon_name: str, tip: str, object_name: str = "") -> QToolButton:
        button = QToolButton()
        if object_name:
            button.setObjectName(object_name)
        button.setIcon(icons.icon(icon_name))
        button.setIconSize(QSize(18, 18))
        button.setToolTip(tip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    # ================= state for the window =================
    @property
    def has_video(self) -> bool:
        return bool(self.model.clips)

    @property
    def has_project(self) -> bool:
        """True once a video was opened, even if every clip has been deleted since."""
        return self.model.source is not None

    @property
    def can_undo(self) -> bool:
        return self.model.can_undo()

    @property
    def can_redo(self) -> bool:
        return self.model.can_redo()

    def export_request(self) -> Optional[ExportRequest]:
        if not self.model.clips:
            return None
        return ExportRequest.from_timeline(self.model)

    def set_drop_highlight(self, on: bool) -> None:
        if self.placeholder.property("dragover") == on:
            return
        self.placeholder.setProperty("dragover", on)
        style = self.placeholder.style()
        style.unpolish(self.placeholder)  # re-evaluate the stylesheet for the new property
        style.polish(self.placeholder)

    # ================= opening =================
    def open_video(self, path: str, confirm_replace: bool = False) -> bool:
        """Open a video as a new project. Returns False if it was not opened (missing file, or the user said no).

        With confirm_replace the user is always asked before a loaded project is replaced.
        Without it they are only asked when they would lose edits.
        """
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            QMessageBox.warning(self, "Open video", f"File not found:\n{path}")
            return False
        if self.has_project and (confirm_replace or self.model.can_undo()) and not self._confirm_replace(path):
            return False

        self.playback.pause()
        media = self._probe(path)
        if media is None:
            QMessageBox.warning(self, "Open video", self._probe_error)
            return False
        if media.duration <= 0:
            QMessageBox.warning(
                self, "Open video", f"{os.path.basename(path)} can't be opened: its length could not be read."
            )
            return False
        self._media = {path: media}
        self._playhead = 0.0
        self.video.clear()
        self.model.load(path, media.duration, media.has_audio, media.audio_channels, media.audio_sample_rate)
        self.playback.seek(0.0)
        self.stage.setCurrentWidget(self.video)
        self.timeline.fit()
        self.video_opened.emit(path)
        self.message.emit(f"{os.path.basename(path)}  ({format_time(media.duration)})", 0)
        self._warn_if_silent()
        return True

    def _ffmpeg_path(self) -> str:
        return self._locate_tools().ffmpeg

    def _media_info(self, path: str) -> Optional[MediaInfo]:
        return self._media.get(path)

    def _warn_if_silent(self) -> None:
        """Say once why the preview has no sound (the speakers could not be opened). Export is not affected."""
        reason = self.playback.no_sound_reason
        if reason and not self._sound_warned:
            self._sound_warned = True
            self.message.emit(f"The preview has no sound: {reason}", 10000)

    def _confirm_replace(self, path: str) -> bool:
        text = f"Replace the current project with {os.path.basename(path)}?"
        if self.model.can_undo():
            text += "\n\nThe edits you made will be lost."
        answer = QMessageBox.question(self, "Open video", text)
        return answer == QMessageBox.StandardButton.Yes

    def _probe(self, path: str) -> Optional[MediaInfo]:
        """What ffprobe says about a video, or None (with the reason in self._probe_error and on the status bar)."""
        self._probe_error = ""
        tools = self._locate_tools()
        if not tools.is_valid():
            self._probe_error = (
                "ffmpeg / ffprobe not found. VidCut needs both to show and to cut a video. "
                "Install FFmpeg, or set the folder that has them in the Settings tab."
            )
            self.message.emit(self._probe_error, 10000)
            return None
        try:
            return media_probe.probe(ProcessRunner(CancelToken()), tools.ffprobe, path)
        except CutError as e:
            self._probe_error = f"ffprobe could not read this video: {e}"
            self.message.emit(self._probe_error, 8000)
            return None

    # ================= playback =================
    def toggle_play(self) -> None:
        self.playback.toggle()

    def pause(self) -> None:
        self.playback.pause()

    def _on_playing_changed(self, playing: bool) -> None:
        self.play_button.setIcon(icons.icon("pause" if playing else "play"))

    def seek_timeline(self, seconds: float) -> None:
        self.playback.seek(seconds)

    def go_to_time(self, seconds: float) -> None:
        """Jump to a time typed in the time field."""
        if not self.has_video:
            return
        total = self.model.total
        if seconds > total + 1e-6:
            self.message.emit("That is past the end of the video, so the playhead moved to the end.", 5000)
        self.seek_timeline(min(seconds, total))

    def focus_time_field(self) -> None:
        if self.has_video:
            self.time_field.setFocus()

    def step_frames(self, count: int) -> None:
        self.seek_timeline(self._playhead + count / self.playback.fps)

    def step_far(self, direction: int) -> None:
        self.step_frames(direction * FAR_STEP_FRAMES)

    def step_seconds(self, direction: int) -> None:
        self.seek_timeline(self._playhead + direction * JUMP_SECONDS)

    def jump_cut(self, direction: int) -> None:
        points = self.model.boundaries()
        eps = 0.001
        if direction < 0:
            earlier = [p for p in points if p < self._playhead - eps]
            self.seek_timeline(earlier[-1] if earlier else 0.0)
        else:
            later = [p for p in points if p > self._playhead + eps]
            self.seek_timeline(later[0] if later else self.model.total)

    def go_start(self) -> None:
        self.seek_timeline(0.0)

    def go_end(self) -> None:
        self.seek_timeline(self.model.total)

    # ================= volume (preview only) =================
    def _on_volume_changed(self, value: int) -> None:
        self.playback.set_master_volume(value / 100.0)
        self.volume_label.setText(f"{value}%")

    def _on_master_muted(self, muted: bool) -> None:
        self.playback.set_master_muted(muted)
        self.mute_button.setIcon(icons.icon("volume_off" if muted else "volume"))
        self.mute_button.setToolTip("Unmute the preview" if muted else "Mute the preview")

    # ================= following the playhead =================
    def _set_playhead(self, seconds: float) -> None:
        self._playhead = max(0.0, seconds)
        self.timeline.set_playhead(self._playhead)
        self._refresh_time_widgets()

    def _refresh_time_widgets(self) -> None:
        self.time_field.show_seconds(self._playhead)
        self.total_label.setText("/ " + format_time(self.model.total))

    # ================= editing =================
    def cut(self) -> None:
        done = self.model.split(self._playhead)
        if done:
            self.message.emit(f"Cut the video at {format_time(self._playhead)}", 4000)
        else:
            self.message.emit("Can't cut here: too close to the edge of a clip, or no video is loaded.", 4000)

    def delete_current(self) -> None:
        index = self.model.index_at(self._playhead)
        if index is None:
            return
        if self.model.delete(index):
            self.message.emit(f"Deleted clip {index + 1}", 4000)
            offsets = self.model.offsets()
            # The clips after the deleted one move forward. Stay at the start of the one that took its place.
            self.seek_timeline(offsets[index] if index < len(offsets) else self.model.total)

    def undo(self) -> None:
        if self.model.undo():
            self.seek_timeline(self._playhead)

    def redo(self) -> None:
        if self.model.redo():
            self.seek_timeline(self._playhead)

    def _on_model_changed(self) -> None:
        self._playhead = min(self._playhead, self.model.total)
        self.timeline.set_playhead(self._playhead)
        self._refresh_time_widgets()
        self.state_changed.emit()

    # ================= right-click menu =================
    def _show_context_menu(self, global_pos: QPoint, seconds: float) -> None:
        if not self.has_project:
            return
        menu = QMenu(self)
        if self.model.clips:
            self.seek_timeline(seconds)
            self._add(menu, "scissors", "Cut here", self.cut)
            self._add(menu, "trash", "Delete clip", self.delete_current)
        menu.exec(global_pos)

    @staticmethod
    def _add(menu: QMenu, icon_name: str, text: str, callback: Callable[[], None]) -> None:
        action = menu.addAction(icons.icon(icon_name), text)
        action.triggered.connect(lambda _checked=False: callback())

    # ================= view =================
    def zoom_in(self) -> None:
        self.timeline.zoom_in()

    def zoom_out(self) -> None:
        self.timeline.zoom_out()

    def zoom_fit(self) -> None:
        self.timeline.fit()

    # ================= shutdown =================
    def shutdown(self) -> None:
        self.playback.shutdown()
