"""Hands the sound of the preview to a sound device without ever waiting for it.

PreviewController gives sound in pieces that are decoded far faster than they are played. A device only takes
what fits in its buffer, so the rest waits here until the device has room. The device itself (a QAudioSink in the
GUI) is behind the small SinkDevice interface, which keeps this part free of Qt.
"""

from __future__ import annotations

from typing import Protocol

from ..engine.preview_media import AUDIO_BYTES_PER_SECOND

FRAME_BYTES = 4  # one sample of 16 bit stereo


class SinkDevice(Protocol):
    """A device that plays 48 kHz stereo signed 16 bit sound that is pushed into it."""

    def buffer_size(self) -> int:  # bytes the device can hold

        ...

    def bytes_free(self) -> int:  # bytes it has room for now
        ...

    def write(self, data: bytes) -> int:  # returns how many bytes it took
        ...

    def reset(self) -> None:  # drop everything that was not played yet
        ...

    def set_volume(self, volume: float) -> None:  # 0.0 to 1.0
        ...


class PcmOutput:
    """The AudioOutput of PreviewController on top of a SinkDevice."""

    def __init__(self, device: SinkDevice) -> None:
        self._device = device
        self._pending = bytearray()

    def reset(self) -> None:
        self._pending.clear()
        self._device.reset()

    def write(self, data: bytes) -> None:
        self._pending += data

    def pump(self) -> None:
        """Give the device as much of the waiting sound as it has room for (whole samples only)."""
        if not self._pending:
            return
        room = self._device.bytes_free()
        count = min(room, len(self._pending))
        count -= count % FRAME_BYTES
        if count <= 0:
            return
        taken = self._device.write(bytes(self._pending[:count]))
        if taken > 0:
            del self._pending[:taken]

    def buffered_seconds(self) -> float:
        """Sound that has been written here and has not been played yet."""
        in_device = max(0, self._device.buffer_size() - self._device.bytes_free())
        return (in_device + len(self._pending)) / AUDIO_BYTES_PER_SECOND

    def set_volume(self, volume: float) -> None:
        self._device.set_volume(min(max(volume, 0.0), 1.0))
