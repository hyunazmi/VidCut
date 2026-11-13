"""Plays the timeline for the preview, with the ffmpeg of the system (see engine.preview_media).

PreviewController speaks in timeline seconds. It decides which picture and which sound belong to the playhead:

    paused    the picture at the playhead is one still picture, made when the playhead moves
    playing   one ffmpeg makes the pictures from the playhead on, another makes the sound. A clock (not the
              pictures) moves the playhead; late pictures are skipped. The clock starts when the first picture
              is there, so that picture and sound start together.

Clips that follow each other in the video play on without a restart.

Nothing here needs Qt. The GUI calls tick() every few milliseconds, paints the pictures it gets from
frame_ready and gives an AudioOutput that plays the sound.
"""

from __future__ import annotations

import re
import time
from collections import deque
from typing import Callable, Deque, Optional, Protocol, Tuple

from ..core.media_info import MediaInfo
from ..engine.events import Signal
from ..engine.preview_media import Frame, FrameStream, PcmStream, StillGrabber, preview_fps, preview_size
from .timeline import TimelineModel

DEFAULT_FPS = 30.0
DEFAULT_VOLUME = 0.8
END_MARGIN_S = 0.001  # a clip is over when the clock is this close to its end
JOIN_TOLERANCE_S = 0.04  # clips this close to each other in the video play on as one
AUDIO_TARGET_S = 0.15  # how much sound is kept ready in the output
AUDIO_CHUNKS_PER_TICK = 4
MIN_SOUND_S = 0.005  # a stretch of sound shorter than this is not worth an ffmpeg
_ADDRESS = re.compile(r"0x[0-9a-fA-F]+")


class AudioOutput(Protocol):
    """What plays the sound: 48 kHz stereo, signed 16 bit (engine.preview_media.AUDIO_*)."""

    def reset(self) -> None:  # throw away what is buffered

        ...

    def write(self, data: bytes) -> None:  # queue sound
        ...

    def pump(self) -> None:  # hand what is queued to the device
        ...

    def buffered_seconds(self) -> float:  # sound that is queued and not played yet
        ...

    def set_volume(self, volume: float) -> None:  # 0.0 to 1.0
        ...


class PreviewController:
    position_changed = Signal(float)  # timeline seconds
    playing_changed = Signal(bool)
    frame_ready = Signal(object)  # a Frame to paint
    error = Signal(str)

    def __init__(
        self,
        model: TimelineModel,
        ffmpeg: Callable[[], str],
        media_of: Callable[[str], Optional[MediaInfo]],
        audio: Optional[AudioOutput] = None,
        clock: Callable[[], float] = time.monotonic,
        blocking: bool = False,
    ) -> None:
        """`blocking` is for tests: pictures and sound are waited for instead of picked up when they are there,
        and single pictures are made at once, so a run does not depend on how fast ffmpeg is."""
        self._model = model
        self._ffmpeg = ffmpeg
        self._media_of = media_of
        self._audio = audio
        self._clock = clock
        self._blocking = blocking
        self.fps = DEFAULT_FPS
        self._position = 0.0
        self._playing = False
        self._clip = 0
        self._frames: Optional[FrameStream] = None
        self._shown = 0  # pictures taken from the stream so far
        self._waiting = False  # playing, but the first picture is not there yet: the clock is stopped
        self._origin = (0.0, 0.0)  # (clock, timeline position) when the clock started
        self._sounds: Deque[PcmStream] = deque()
        self._sound_end = -1.0  # timeline time up to which the sound that was opened last reaches
        self._master = DEFAULT_VOLUME
        self._muted = False
        self._stills = StillGrabber(synchronous=blocking)
        self._still_token = 0
        self._last_error = ""
        self._seen_clips = model.clips
        model.on_change(self._on_model_changed)
        self._apply_volume()

    # ---- state ------------------------------------------------------
    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def position(self) -> float:
        return self._position

    @property
    def output_volume(self) -> float:
        """What is sent to the speakers: the master volume, or 0 when muted."""
        return 0.0 if self._muted else self._master

    def set_master_volume(self, volume: float) -> None:
        self._master = min(max(volume, 0.0), 1.0)
        self._apply_volume()

    def set_master_muted(self, muted: bool) -> None:
        self._muted = muted
        self._apply_volume()

    def _apply_volume(self) -> None:
        if self._audio is not None:
            self._audio.set_volume(self.output_volume)

    def _path(self) -> str:
        source = self._model.source
        return source.path if source is not None else ""

    # ---- control ----------------------------------------------------
    def seek(self, seconds: float) -> None:
        """Put the playhead at `seconds` (timeline). Keeps playing when it was playing."""
        if not self._model.clips:
            self._stop_all()
            self._set_position(0.0)
            return
        t = min(max(seconds, 0.0), self._model.total)
        if self._playing:
            self._start_playing_at(t)
            return
        self._stop_all()
        located = self._model.locate(t)
        if located is None:
            return
        self._clip = located[0]
        self._set_position(t)
        self._request_still(located[0], located[1])

    def toggle(self) -> None:
        if self._playing:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        if self._playing or not self._model.clips:
            return
        if self._position >= self._model.total - 0.02:
            self._position = 0.0
        self._set_playing(True)
        self._start_playing_at(self._position)

    def pause(self) -> None:
        if not self._playing:
            return
        self._set_playing(False)
        self._stop_all()
        located = self._model.locate(self._position)
        if located is not None:
            self._request_still(located[0], located[1])  # the exact picture at the playhead

    def shutdown(self) -> None:
        self._playing = False
        self._stop_all()
        self._stills.close()

    # ---- the clock --------------------------------------------------
    def tick(self) -> None:
        """Call this every few milliseconds from the GUI thread."""
        result = self._stills.poll()
        if result is not None and result.token == self._still_token and not self._playing:
            if result.frame is not None:
                self._last_error = ""
                self.frame_ready.emit(result.frame)
            else:
                self._report_error(result.error or "ffmpeg could not make the picture")
        if self._playing:
            self._tick_playing()
        if self._audio is not None:
            self._audio.pump()

    def _tick_playing(self) -> None:
        frames = self._frames
        if frames is None:
            return
        now = self._clock()
        if self._waiting:
            frame = self._next_frame(frames)
            if frame is None:
                if frames.exhausted:
                    self._fail(frames.error_text() or "ffmpeg produced no picture")
                return
            self._shown = 1
            self._last_error = ""
            self.frame_ready.emit(frame)
            self._waiting = False
            self._origin = (now, self._position)
        position = self._origin[1] + (now - self._origin[0])
        clips, offsets = self._model.clips, self._model.offsets()
        clip, offset = clips[self._clip], offsets[self._clip]
        if position >= offset + clip.length - END_MARGIN_S:
            self._clip_over(now)
            return
        self._position = position
        self._show_pictures(frames, clip.start + (position - offset))
        self.position_changed.emit(position)
        if frames.exhausted:  # the video ended before its clip did
            self._clip_over(now)
            return
        self._keep_sound_going(position)

    def _show_pictures(self, frames: FrameStream, source_time: float) -> None:
        """Show the picture that belongs to this source time; pictures that are late are skipped."""
        wanted = int(max(0.0, source_time - frames.start) * frames.fps + 1e-6) + 1
        latest: Optional[Frame] = None
        while self._shown < wanted:
            frame = self._next_frame(frames)
            if frame is None:
                break
            self._shown += 1
            latest = frame
        if latest is not None:
            self.frame_ready.emit(latest)

    def _next_frame(self, frames: FrameStream) -> Optional[Frame]:
        return frames.wait_for_frame() if self._blocking else frames.take_frame()

    def _clip_over(self, now: float) -> None:
        clips, offsets = self._model.clips, self._model.offsets()
        following = self._clip + 1
        if following >= len(clips):
            self._finish()
            return
        current, nxt = clips[self._clip], clips[following]
        joined = (
            abs(nxt.start - current.end) < JOIN_TOLERANCE_S and self._frames is not None and not self._frames.exhausted
        )
        self._clip = following
        self._set_position(offsets[following])
        if joined:
            self._origin = (now, self._position)  # the same ffmpeg goes on
        else:
            self._start_video_at(self._position)

    def _finish(self) -> None:
        self._set_position(self._model.total)
        self._set_playing(False)
        self._stop_all()

    # ---- starting and stopping --------------------------------------
    def _start_playing_at(self, t: float) -> None:
        """(Re)start picture and sound at timeline time t, while playing."""
        self._stop_all()
        located = self._model.locate(t)
        if located is None:
            return
        self._clip = located[0]
        self._set_position(max(t, self._model.offsets()[located[0]]))
        self._start_video_at(self._position)

    def _start_video_at(self, t: float) -> None:
        """A new ffmpeg for the pictures from timeline time t on. The sound is left alone."""
        self._close_frames()
        located = self._model.locate(t)
        if located is None:
            return
        _index, source_time = located
        path = self._path()
        media = self._media_of(path)
        if media is None:
            self._fail(f"Nothing is known about {path}")
            return
        fps = preview_fps(media.video)
        self.fps = fps
        try:
            self._frames = FrameStream(self._ffmpeg(), path, source_time, preview_size(media.video), fps)
        except OSError as e:
            self._fail(f"Cannot start ffmpeg: {e}")
            return
        self._shown = 0
        self._waiting = True

    def _close_frames(self) -> None:
        if self._frames is not None:
            self._frames.close()
            self._frames = None
        self._waiting = False

    def _stop_all(self) -> None:
        self._close_frames()
        self._reset_sound()

    def _fail(self, text: str) -> None:
        self._set_playing(False)
        self._stop_all()
        self._report_error(text)

    def _report_error(self, text: str) -> None:
        key = _ADDRESS.sub("", text)  # ffmpeg names its own memory address in a message
        if key != self._last_error:  # the same message once, not at every tick
            self._last_error = key
            self.error.emit(text)

    def _set_playing(self, playing: bool) -> None:
        if playing != self._playing:
            self._playing = playing
            self.playing_changed.emit(playing)

    def _set_position(self, position: float) -> None:
        self._position = position
        self.position_changed.emit(position)

    # ---- one picture ------------------------------------------------
    def _request_still(self, index: int, source_time: float) -> None:
        clip = self._model.clips[index]
        path = self._path()
        media = self._media_of(path)
        if media is None:
            self._report_error(f"Nothing is known about {path}")
            return
        fps = preview_fps(media.video)
        self.fps = fps
        source_time = max(clip.start, min(source_time, clip.end - 0.5 / fps))  # inside the clip's last picture
        self._still_token = self._stills.request(self._ffmpeg(), path, source_time, preview_size(media.video), fps)
        if self._blocking:
            self.tick()

    # ---- sound ------------------------------------------------------
    def _keep_sound_going(self, position: float) -> None:
        if self._audio is None:
            return
        if position >= self._sound_end:
            self._open_sound(position)
        self._feed_audio()

    def _sound_spot(self, position: float) -> Optional[Tuple[str, float, float, float, float]]:
        """The sound at a timeline time: (file, start in it, seconds, volume, timeline time where this stretch ends)."""
        model = self._model
        source = model.source
        if source is None or not source.has_audio:
            return None
        located = model.locate(position)
        if located is None:
            return None
        i, start = located
        clips, offsets = model.clips, model.offsets()
        duration = clips[i].end - start
        end = offsets[i] + clips[i].length
        while i + 1 < len(clips) and abs(clips[i + 1].start - clips[i].end) < JOIN_TOLERANCE_S:
            i += 1  # clips that follow each other in the video
            duration += clips[i].length
            end = offsets[i] + clips[i].length
        return source.path, start, duration, 1.0, end

    def _open_sound(self, position: float) -> None:
        spot = self._sound_spot(position)
        if spot is None or spot[2] < MIN_SOUND_S:
            self._sound_end = position  # silent here: look again at the next tick
            return
        path, start, duration, gain, end = spot
        try:
            self._sounds.append(PcmStream(self._ffmpeg(), path, start, duration, gain))
        except OSError as e:
            self._audio = None  # no sound, but the picture goes on
            self._report_error(f"Cannot start ffmpeg for the sound: {e}")
            return
        self._sound_end = end

    def _feed_audio(self) -> None:
        audio = self._audio
        if audio is None:
            return
        fed = 0
        while self._sounds and fed < AUDIO_CHUNKS_PER_TICK and audio.buffered_seconds() < AUDIO_TARGET_S:
            stream = self._sounds[0]
            chunk = stream.wait_for() if self._blocking else stream.take()
            if chunk is None:
                if stream.exhausted:
                    stream.close()
                    self._sounds.popleft()
                    continue
                break
            audio.write(chunk)
            fed += 1

    def _reset_sound(self) -> None:
        for stream in self._sounds:
            stream.close()
        self._sounds.clear()
        self._sound_end = -1.0
        if self._audio is not None:
            self._audio.reset()

    # ---- the model changed ------------------------------------------
    def _on_model_changed(self) -> None:
        clips = self._model.clips
        if clips != self._seen_clips:
            self._seen_clips = clips
            if not clips:
                self._set_playing(False)
            self.seek(self._position)
