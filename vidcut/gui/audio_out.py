"""The speakers of the preview: a QAudioSink behind the small SinkDevice interface of editor.audio_output.

Qt only plays the sound here. Decoding it is done by the ffmpeg of the system (engine.preview_media).
"""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import QIODevice, QObject

from ..editor.audio_output import PcmOutput
from ..engine.preview_media import AUDIO_BYTES_PER_SECOND, AUDIO_CHANNELS, AUDIO_RATE

DEVICE_BUFFER_S = 0.25


class QtSinkDevice:
    """A QAudioSink that is played by pushing bytes into it.

    The sink is opened when the first sound is written and closed by reset(), so nothing stays open (or is
    opened and closed again) while the preview is paused or the playhead is moved around.
    """

    def __init__(self, parent: QObject) -> None:
        from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices  # noqa: PLC0415 - may be missing

        fmt = QAudioFormat()
        fmt.setSampleRate(AUDIO_RATE)
        fmt.setChannelCount(AUDIO_CHANNELS)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        device = QMediaDevices.defaultAudioOutput()
        if device.isNull():
            raise RuntimeError("there is no audio output device")
        if not device.isFormatSupported(fmt):
            raise RuntimeError("the audio output device does not play 48 kHz stereo")
        self._sink = QAudioSink(device, fmt, parent)
        self._sink.setBufferSize(int(AUDIO_BYTES_PER_SECOND * DEVICE_BUFFER_S))
        self._io: Optional[QIODevice] = None  # None while the sink is closed

    def buffer_size(self) -> int:
        return int(self._sink.bufferSize())

    def bytes_free(self) -> int:
        return self.buffer_size() if self._io is None else int(self._sink.bytesFree())

    def write(self, data: bytes) -> int:
        if self._io is None:
            self._io = self._sink.start()
        return int(self._io.write(data))

    def reset(self) -> None:
        if self._io is not None:
            self._sink.stop()  # drops what was not played yet
            self._io = None

    def set_volume(self, volume: float) -> None:
        self._sink.setVolume(volume)


def create_audio_output(parent: QObject) -> Tuple[Optional[PcmOutput], str]:
    """(the speakers, "") or (None, why the preview has no sound)."""
    try:
        return PcmOutput(QtSinkDevice(parent)), ""
    except Exception as e:  # ImportError, or a device that cannot be used
        return None, str(e)
