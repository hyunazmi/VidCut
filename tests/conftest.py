"""Shared test setup: makes the package importable and creates a small sample video with ffmpeg."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FFMPEG = shutil.which("ffmpeg") or ""
FFPROBE = shutil.which("ffprobe") or ""
needs_ffmpeg = pytest.mark.skipif(not (FFMPEG and FFPROBE), reason="ffmpeg and ffprobe are not installed")


@pytest.fixture(scope="session")
def sample_video() -> str:
    """A 20 second test video with a picture and a sine tone."""
    if not FFMPEG:
        pytest.skip("ffmpeg is not installed")
    folder = tempfile.mkdtemp(prefix="vidcut_test_")
    path = os.path.join(folder, "sample.mp4")
    subprocess.run(
        [
            FFMPEG,
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=640x360:rate=30:duration=20",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=20",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-g",
            "30",
            "-c:a",
            "aac",
            "-shortest",
            path,
        ],
        check=True,
    )
    yield path
    shutil.rmtree(folder, ignore_errors=True)


@pytest.fixture
def out_dir(tmp_path) -> str:
    return str(tmp_path)
