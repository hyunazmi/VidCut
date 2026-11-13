"""Persistent user settings (stored with QSettings) and the FFmpeg lookup that uses them."""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings

from ..core.encode_settings import EncodeSettings, validate_settings
from ..engine import ffmpeg_locator
from ..engine.ffmpeg_locator import FfmpegTools

_FFMPEG_DIR_KEY = "ffmpeg_dir"
_PRESET_KEY, _CRF_KEY, _AUDIO_BITRATE_KEY = "encode_preset", "encode_crf", "encode_audio_bitrate"


def _store() -> QSettings:
    return QSettings("VidCut", "VidCut")


def saved_ffmpeg_dir() -> str:
    return str(_store().value(_FFMPEG_DIR_KEY, "") or "")


def save_ffmpeg_dir(path: str) -> None:
    """Remember the folder that holds ffmpeg and ffprobe. An empty path means automatic."""
    store = _store()
    if path:
        store.setValue(_FFMPEG_DIR_KEY, path)
    else:
        store.remove(_FFMPEG_DIR_KEY)
    store.sync()


def locate_tools() -> FfmpegTools:
    """Saved folder first, then VIDCUT_FFMPEG_DIR, then the automatic search."""
    custom = saved_ffmpeg_dir() or os.environ.get("VIDCUT_FFMPEG_DIR", "")
    return ffmpeg_locator.locate(custom)


def load_encode_settings() -> EncodeSettings:
    """The export quality chosen in the Settings tab. Falls back to the defaults if it is not valid."""
    defaults = EncodeSettings()
    store = _store()
    try:
        saved = EncodeSettings(
            preset=str(store.value(_PRESET_KEY, defaults.preset)),
            crf=int(str(store.value(_CRF_KEY, defaults.crf))),
            audio_bitrate=str(store.value(_AUDIO_BITRATE_KEY, defaults.audio_bitrate)),
        )
    except (TypeError, ValueError):
        return defaults
    return saved if validate_settings(saved) is None else defaults


def save_encode_settings(encode: EncodeSettings) -> None:
    store = _store()
    store.setValue(_PRESET_KEY, encode.preset)
    store.setValue(_CRF_KEY, encode.crf)
    store.setValue(_AUDIO_BITRATE_KEY, encode.audio_bitrate)
    store.sync()
