"""Turns the edited timeline into a pipeline that is ready to run."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from ..core.encode_settings import EncodeSettings
from ..core.formats import extension
from ..engine.smart_cutter import BatchCutter, BatchJob, CutJob, SmartCutter
from .export_pipeline import ExportPipeline
from .timeline import Clip, TimelineModel

TEMP_PREFIX = ".vidcut_gui_"


class ExportPlanError(Exception):
    """The export cannot be set up (the message is meant to be shown to the user)."""


@dataclass(frozen=True)
class ExportRequest:
    """What the editor wants exported: the video and the clips that play, in order."""

    source: str
    clips: Tuple[Clip, ...]

    @classmethod
    def from_timeline(cls, model: TimelineModel) -> ExportRequest:
        if model.source is None:
            raise ExportPlanError("No video is loaded.")
        return cls(model.source.path, tuple(model.export_clips()))

    def build(self, output: str, ffmpeg: str, ffprobe: str, encode: EncodeSettings) -> ExportPlan:
        return build_plan(self.source, output, self.clips, ffmpeg, ffprobe, encode)


@dataclass
class ExportPlan:
    pipeline: ExportPipeline
    cleanup_dirs: List[str]  # temporary folders to remove once the pipeline has finished


def default_output_path(source_path: str, output_ext: str) -> str:
    return f"{os.path.splitext(source_path)[0]}_edit.{output_ext}"


def _same_file(a: str, b: str) -> bool:
    try:
        if os.path.exists(a) and os.path.exists(b):
            return os.path.samefile(a, b)
    except OSError:
        pass
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def build_plan(
    source: str, output: str, clips: Sequence[Clip], ffmpeg: str, ffprobe: str, encode: EncodeSettings
) -> ExportPlan:
    """Plan an export of `clips` of one video.

    One clip is cut directly into the output with Smart Cut. Several clips are each cut into a temporary
    folder and then joined. The temporary folder is created next to the output file, so the joined file
    is moved onto the output on the same disk.
    """
    if not clips:
        raise ExportPlanError("There is nothing to export.")
    if _same_file(source, output):
        raise ExportPlanError("The output file can't be the source video.")

    temp_dir = ""
    if len(clips) > 1:
        try:
            temp_dir = tempfile.mkdtemp(prefix=TEMP_PREFIX, dir=os.path.dirname(os.path.abspath(output)))
        except OSError as e:
            raise ExportPlanError(f"Can't write to the output folder:\n{e}") from e

    ext = extension(output)
    cutter: SmartCutter
    if len(clips) == 1:
        cutter = SmartCutter(
            CutJob(
                input=source,
                output=output,
                start=clips[0].start,
                end=clips[0].end,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
                settings=encode,
            )
        )
        parts = 1
    else:
        names = [f"part_{i:03d}" for i in range(1, len(clips) + 1)]
        jobs = [
            CutJob(
                input=source,
                output=os.path.join(temp_dir, f"{name}.{ext}"),
                start=c.start,
                end=c.end,
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
                settings=encode,
            )
            for name, c in zip(names, clips)
        ]
        cutter = BatchCutter(BatchJob(jobs, names, merge_output=output))
        parts = len(clips)

    duration = sum(c.length for c in clips)
    pipeline = ExportPipeline(cutter, parts=parts, output=output, duration=duration)
    return ExportPlan(pipeline, [temp_dir] if temp_dir else [])
