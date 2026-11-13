"""Decoding for the preview, done by the ffmpeg of the system.

Qt's own media player carries a private copy of FFmpeg that cannot decode everything (AV1 for one) and ignores
the one that is installed. The preview therefore asks the system's ffmpeg for what it shows:

    grab_frame / StillGrabber   one picture at a time (a seek, a step, a pause)
    FrameStream                 the pictures of a video from a given time on (playing)
    PcmStream                   the sound from a given time on, as raw 16 bit stereo (playing)

Nothing here needs Qt. The pictures are raw RGB bytes and the sound is raw PCM; the GUI paints and plays them.
"""

from __future__ import annotations

import math
import queue
import subprocess  # nosec B404
import threading
from fractions import Fraction
from typing import Any, List, NamedTuple, Optional, Tuple

from ..core.media_info import VideoInfo
from .process_runner import popen_kwargs
import contextlib

MAX_PREVIEW_SIZE = (1280, 720)  # pictures are decoded no bigger than this; the screen scales them
MAX_PREVIEW_FPS = 60.0
DEFAULT_FPS = 30.0
FALLBACK_SIZE = (640, 360)
_GRID_SLACK = 1e-6  # keeps a time that is exactly on a frame (3.04 s at 25 fps) on that frame
AUDIO_RATE = 48000
AUDIO_CHANNELS = 2
AUDIO_BYTES_PER_SECOND = AUDIO_RATE * AUDIO_CHANNELS * 2  # signed 16 bit
AUDIO_CHUNK_BYTES = 8192  # about 43 ms of sound
_QUEUE_FRAMES = 6
_QUEUE_CHUNKS = 32
_ERROR_LINES = 6
_END = object()


class Frame(NamedTuple):
    width: int
    height: int
    data: bytes  # width * height * 3 bytes of RGB


def preview_fps(video: VideoInfo) -> float:
    fps = video.fps if video.fps > 0 else DEFAULT_FPS
    return min(fps, MAX_PREVIEW_FPS)


def preview_size(video: VideoInfo, limit: Tuple[int, int] = MAX_PREVIEW_SIZE) -> Tuple[int, int]:
    """Size of the pictures as they are shown (rotation and pixel shape applied), even numbers, within `limit`."""
    width, height = float(video.width), float(video.height)
    if width <= 0 or height <= 0:
        return FALLBACK_SIZE
    if abs(video.rotation) % 180 == 90:
        width, height = height, width
    if video.sar > 0:
        width *= video.sar
    scale = min(1.0, limit[0] / width, limit[1] / height)
    w, h = max(2, int(round(width * scale))), max(2, int(round(height * scale)))
    return w - w % 2, h - h % 2


def frame_number(t: float, fps: float) -> int:
    """The number of the picture that is on screen at time t.

    The picture at k / fps stays on screen until the next one.
    """
    return max(0, int(math.floor(t * fps + _GRID_SLACK)))


def frame_time(t: float, fps: float) -> float:
    """The time of the picture that is on screen at time t: t moved back onto the picture grid."""
    return frame_number(t, fps) / fps


def _seek_time(t: float, fps: float) -> float:
    """Where to tell ffmpeg to seek so that its first picture is the one on screen at t.

    ffmpeg gives the first picture at or after the seek time, so the time is put in the middle between the
    picture before and the picture that is wanted.
    """
    return max(0.0, (frame_number(t, fps) - 0.5) / fps)


def still_args(path: str, t: float, size: Tuple[int, int], fps: float) -> List[str]:
    """ffmpeg arguments for the one picture that is on screen at time t of the video."""
    return [
        "-v",
        "error",
        "-nostdin",
        "-ss",
        f"{_seek_time(t, fps):.6f}",
        "-i",
        path,
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-vf",
        f"scale={size[0]}:{size[1]}",
        "-frames:v",
        "1",
        "-pix_fmt",
        "rgb24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]


def _exact_rate(fps: float) -> str:
    """The rate as an exact fraction (30000/1001): a decimal that is a hair off can drop the first picture."""
    rate = Fraction(fps).limit_denominator(10000)
    return f"{rate.numerator}/{rate.denominator}"


def frames_args(path: str, start: float, size: Tuple[int, int], fps: float) -> List[str]:
    """ffmpeg arguments for every picture from `start` on, at a steady `fps` (so picture n is at start + n / fps).

    The seek is half a picture before the first one, so every picture arrives half a picture late. Rounding down
    puts each of them on its own number, however much its time is off by up to half a picture. The very first
    picture of a video has nothing before it to seek to, so there the nearest number is taken instead.
    """
    rounding = "down" if frame_number(start, fps) > 0 else "near"
    return [
        "-v",
        "error",
        "-nostdin",
        "-ss",
        f"{_seek_time(start, fps):.6f}",
        "-i",
        path,
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-vf",
        f"fps={_exact_rate(fps)}:round={rounding},scale={size[0]}:{size[1]}",
        "-pix_fmt",
        "rgb24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]


def pcm_args(path: str, start: float, duration: float, gain: float) -> List[str]:
    """ffmpeg arguments for `duration` seconds of sound from `start`, as 48 kHz stereo signed 16 bit."""
    args = [
        "-v",
        "error",
        "-nostdin",
        "-ss",
        f"{max(0.0, start):.6f}",
        "-t",
        f"{max(0.0, duration):.6f}",
        "-i",
        path,
        "-map",
        "0:a:0",
        "-vn",
        "-sn",
        "-dn",
    ]
    if abs(gain - 1.0) > 1e-9:
        args += ["-af", f"volume={gain:.4f}"]
    return args + ["-ar", str(AUDIO_RATE), "-ac", str(AUDIO_CHANNELS), "-f", "s16le", "pipe:1"]


def _start(ffmpeg: str, args: List[str]) -> subprocess.Popen[bytes]:
    return subprocess.Popen([ffmpeg, *args], **popen_kwargs())  # nosec B603


def _tail(chunks: List[bytes]) -> str:
    lines = b"".join(chunks).decode("utf-8", "replace").strip().splitlines()
    return "\n".join(lines[-_ERROR_LINES:])


def _drain_errors(stream: Any, sink: List[bytes]) -> None:
    try:
        for chunk in iter(lambda: stream.read(4096), b""):
            if sum(map(len, sink)) < 65536:
                sink.append(chunk)
    except (OSError, ValueError):
        pass


# ---- one picture ------------------------------------------------------------


class StillResult(NamedTuple):
    token: int
    frame: Optional[Frame]  # None when ffmpeg could not make the picture
    error: str


def _read_picture(proc: subprocess.Popen[bytes], size: Tuple[int, int]) -> Tuple[Optional[Frame], str]:
    out, err = proc.communicate()
    need = size[0] * size[1] * 3
    if len(out) >= need:
        return Frame(size[0], size[1], out[:need]), ""
    return None, _tail([err or b""])


class StillGrabber:
    """Makes single pictures on a worker thread. Only the newest request matters: when another one comes in,
    the picture that is still being made is stopped.

    With synchronous=True a request is carried out at once, in the calling thread (for tests).
    """

    def __init__(self, synchronous: bool = False) -> None:
        self._sync = synchronous
        self._cond = threading.Condition()
        self._pending: Optional[Tuple[int, str, str, float, Tuple[int, int], float]] = None
        self._running: Optional[subprocess.Popen[bytes]] = None
        self._result: Optional[StillResult] = None
        self._token = 0
        self._closed = False
        self._thread: Optional[threading.Thread] = None

    def request(self, ffmpeg: str, path: str, t: float, size: Tuple[int, int], fps: float) -> int:
        """Ask for the picture at time t. Returns a token; poll() reports the result with the same token."""
        with self._cond:
            self._token += 1
            token = self._token
            job = (token, ffmpeg, path, t, size, fps)
            if self._sync:
                pass
            else:
                self._pending = job
                if self._running is not None:
                    self._running.kill()  # an older picture that nobody wants any more
                if self._thread is None:
                    self._thread = threading.Thread(target=self._work, daemon=True)
                    self._thread.start()
                self._cond.notify()
        if self._sync:
            self._result = self._make(job)
        return token

    def poll(self) -> Optional[StillResult]:
        """The finished picture, once. None when there is nothing new."""
        with self._cond:
            result, self._result = self._result, None
            return result

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._pending = None
            if self._running is not None:
                self._running.kill()
            self._cond.notify()
        if self._thread is not None:
            self._thread.join()

    # ---- the worker ---------------------------------------------------
    def _work(self) -> None:
        while True:
            with self._cond:
                while self._pending is None and not self._closed:
                    self._cond.wait()
                if self._closed:
                    return
                job, self._pending = self._pending, None
            if job is None:  # only when closed, which returned above
                return
            result = self._make(job)
            with self._cond:
                if not self._closed:
                    self._result = result

    def _make(self, job: Tuple[int, str, str, float, Tuple[int, int], float]) -> StillResult:
        token, ffmpeg, path, t, size, fps = job
        try:
            proc = _start(ffmpeg, still_args(path, t, size, fps))
        except OSError as e:
            return StillResult(token, None, f"Cannot start '{ffmpeg}': {e}")
        with self._cond:
            self._running = proc
            superseded = self._pending is not None or self._closed
        if superseded:
            proc.kill()
        frame, error = _read_picture(proc, size)
        with self._cond:
            self._running = None
        return StillResult(token, frame, error)


# ---- streams ------------------------------------------------------------------


class _PipeStream:
    """An ffmpeg process whose output is cut into equal pieces by a reader thread.

    take() is for the GUI thread: it never waits. wait_for() is for tests: it waits for the next piece.
    """

    def __init__(self, ffmpeg: str, args: List[str], piece_bytes: int, max_pieces: int, keep_partial: bool) -> None:
        self._piece = piece_bytes
        self._keep_partial = keep_partial
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=max_pieces)
        self._closed = threading.Event()
        self._done = False
        self._errors: List[bytes] = []
        self._proc = _start(ffmpeg, args)
        self._readers = [
            threading.Thread(target=self._read_output, daemon=True),
            threading.Thread(target=_drain_errors, args=(self._proc.stderr, self._errors), daemon=True),
        ]
        for thread in self._readers:
            thread.start()

    def _put(self, item: Any) -> bool:
        while not self._closed.is_set():
            try:
                self._queue.put(item, timeout=0.1)
                return True
            except queue.Full:
                continue
        return False

    def _read_output(self) -> None:
        stdout = self._proc.stdout
        if stdout is None:  # the pipe is always opened by _start
            return
        try:
            while not self._closed.is_set():
                data = stdout.read(self._piece)
                if len(data) < self._piece:
                    if data and self._keep_partial and len(data) >= 4:
                        self._put(data[: len(data) - len(data) % 4])
                    break
                if not self._put(data):
                    break
        except (OSError, ValueError):
            pass
        finally:
            try:
                self._proc.wait()  # so that what ffmpeg said is complete when the end is seen
                self._readers[1].join()
            except (OSError, ValueError):
                pass
            self._put(_END)

    def take(self) -> Optional[bytes]:
        """The next piece if one is ready, else None. After the last piece, `exhausted` becomes True."""
        return self._get(block=False)

    def wait_for(self) -> Optional[bytes]:
        """The next piece, waiting for it. None when the stream is over."""
        return self._get(block=True)

    def _get(self, block: bool) -> Optional[bytes]:
        if self._done:
            return None
        try:
            item = self._queue.get(block=block)
        except queue.Empty:
            return None
        if item is _END:
            self._done = True
            return None
        return item

    @property
    def exhausted(self) -> bool:
        """True when everything has been taken and nothing more will come."""
        return self._done

    def error_text(self) -> str:
        return _tail(self._errors)

    def close(self) -> None:
        """Stop ffmpeg and the reader threads."""
        self._closed.set()
        with contextlib.suppress(OSError):
            self._proc.kill()
        self._proc.wait()
        for thread in self._readers:
            thread.join()
        for pipe in (self._proc.stdout, self._proc.stderr):
            if pipe is not None:
                pipe.close()
        self._done = True


class FrameStream(_PipeStream):
    """The pictures of a video from `start` on. Picture n is the one at self.start + n / fps."""

    def __init__(self, ffmpeg: str, path: str, start: float, size: Tuple[int, int], fps: float) -> None:
        self.size = size
        self.fps = fps
        self.start = frame_time(start, fps)  # picture 0 is the one that is on screen at `start`
        super().__init__(ffmpeg, frames_args(path, start, size, fps), size[0] * size[1] * 3, _QUEUE_FRAMES, False)

    def take_frame(self) -> Optional[Frame]:
        data = self.take()
        return None if data is None else Frame(self.size[0], self.size[1], data)

    def wait_for_frame(self) -> Optional[Frame]:
        data = self.wait_for()
        return None if data is None else Frame(self.size[0], self.size[1], data)


class PcmStream(_PipeStream):
    """`duration` seconds of the sound of a video from `start` on, as 48 kHz stereo signed 16 bit."""

    def __init__(self, ffmpeg: str, path: str, start: float, duration: float, gain: float = 1.0) -> None:
        super().__init__(ffmpeg, pcm_args(path, start, duration, gain), AUDIO_CHUNK_BYTES, _QUEUE_CHUNKS, True)
