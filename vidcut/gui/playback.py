"""Plays the timeline in the Editor tab.

The work is done by editor.preview.PreviewController, which asks the ffmpeg of the system for every picture and
every bit of sound (Qt's own media player is not used: it has a private FFmpeg that cannot decode everything).
This class only gives it what it needs from Qt: a timer, a surface to paint on and a speaker.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject, QTimer, Signal

from ..core.media_info import MediaInfo
from ..editor.preview import DEFAULT_VOLUME, PreviewController
from ..editor.timeline import TimelineModel
from .audio_out import create_audio_output
from .video_surface import VideoSurface

__all__ = ["DEFAULT_VOLUME", "PlaybackController"]

TICK_MS = 10  # how often the playhead and the picture are brought up to date


def _one_line(text: str) -> str:
    """ffmpeg's messages have several lines; the status bar has room for one: the last one says the most."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return lines[-1] if lines else text


class PlaybackController(QObject):
    """Speaks in timeline seconds; clips, their order and the video files behind them are handled below it."""

    position_changed = Signal(float)  # timeline seconds
    playing_changed = Signal(bool)
    error = Signal(str)

    def __init__(
        self,
        model: TimelineModel,
        surface: VideoSurface,
        ffmpeg: Callable[[], str],
        media_of: Callable[[str], Optional[MediaInfo]],
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        speakers, self._no_sound_reason = create_audio_output(self)
        self._core = PreviewController(model, ffmpeg, media_of, speakers)
        self._core.position_changed.connect(self.position_changed.emit)
        self._core.playing_changed.connect(self.playing_changed.emit)
        self._core.frame_ready.connect(surface.show_frame)
        self._core.error.connect(lambda text: self.error.emit(_one_line(text)))
        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._core.tick)
        self._timer.start()

    @property
    def fps(self) -> float:
        return self._core.fps

    @property
    def no_sound_reason(self) -> str:
        """Why the preview is silent, or '' when it has sound."""
        return self._no_sound_reason

    @property
    def output_volume(self) -> float:
        return self._core.output_volume

    def seek(self, seconds: float) -> None:
        self._core.seek(seconds)

    def toggle(self) -> None:
        self._core.toggle()

    def pause(self) -> None:
        self._core.pause()

    def set_master_volume(self, volume: float) -> None:
        self._core.set_master_volume(volume)

    def set_master_muted(self, muted: bool) -> None:
        self._core.set_master_muted(muted)

    def shutdown(self) -> None:
        self._timer.stop()
        self._core.shutdown()
