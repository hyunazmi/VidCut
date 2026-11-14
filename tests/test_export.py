import os
import shutil
import subprocess

import pytest
from conftest import FFMPEG, FFPROBE, needs_ffmpeg

from vidcut.core.encode_settings import EncodeSettings
from vidcut.editor.export_plan import ExportPlanError, ExportRequest, build_plan
from vidcut.editor.progress import ProgressTracker
from vidcut.editor.timeline import Clip


def _duration(path: str) -> float:
    out = subprocess.check_output(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path]
    )
    return float(out.decode().strip())


def _fast() -> EncodeSettings:
    return EncodeSettings(preset="ultrafast", crf=28)


@needs_ffmpeg
def test_single_clip_export(sample_video, out_dir):
    out = os.path.join(out_dir, "single.mp4")
    plan = ExportRequest(sample_video, (Clip(2.0, 7.0),)).build(out, FFMPEG, FFPROBE, _fast())
    results = {}
    plan.pipeline.succeeded.connect(lambda text: results.setdefault("ok", text))
    plan.pipeline.failed.connect(lambda text: results.setdefault("fail", text))
    plan.pipeline.run()
    assert "fail" not in results, results
    assert abs(_duration(out) - 5.0) < 0.2


@needs_ffmpeg
def test_multi_clip_export_joins_parts_and_reports_progress(sample_video, out_dir):
    out = os.path.join(out_dir, "multi.mp4")
    clips = (Clip(0.0, 3.0), Clip(10.0, 12.5), Clip(17.0, 20.0))
    plan = ExportRequest(sample_video, clips).build(out, FFMPEG, FFPROBE, _fast())
    seen, results = [], {}
    pipe = plan.pipeline
    pipe.stage_changed.connect(lambda label, part, count: seen.append((label, part, count)))
    pipe.progress.connect(lambda fraction, eta: seen.append(("progress", fraction)))
    pipe.succeeded.connect(lambda text: results.setdefault("ok", text))
    pipe.failed.connect(lambda text: results.setdefault("fail", text))
    try:
        pipe.run()
    finally:
        for folder in plan.cleanup_dirs:
            shutil.rmtree(folder, ignore_errors=True)
    assert "fail" not in results, results.get("fail")
    assert abs(_duration(out) - 8.5) < 0.3
    labels = [s for s in seen if s[0] != "progress"]
    assert ("Cutting part 1 of 3", 1, 3) in labels
    assert ("Joining the parts", 3, 3) in labels
    fractions = [s[1] for s in seen if s[0] == "progress"]
    assert fractions == sorted(fractions), "progress must never go backwards"
    assert fractions[-1] == 1.0
    assert not [n for n in os.listdir(out_dir) if n.startswith(".vidcut")], "temporary folders left behind"


def test_output_can_not_be_the_source(sample_video):
    with pytest.raises(ExportPlanError):
        build_plan(sample_video, sample_video, [Clip(0, 1)], "ffmpeg", "ffprobe", EncodeSettings())


def test_progress_tracker_labels():
    t = ProgressTracker(3, merge=True)
    t.start_part(2)
    t.start_step(1, 4, "[A] Re-encoding 0.8s (start)...")
    assert t.label == "Cutting part 2 of 3"
    assert t.detail == "Re-encoding 0.8s (start)"
    t.start_merge()
    assert t.label == "Joining the parts"
    assert (t.current_part, t.part_count) == (3, 3)
