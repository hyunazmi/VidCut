import os
import shutil

from conftest import needs_ffmpeg

from vidcut.engine.ffmpeg_locator import locate, resolve_tools_dir


@needs_ffmpeg
def test_finds_system_ffmpeg():
    tools = locate("")
    assert tools.is_valid()
    assert os.access(tools.ffmpeg, os.X_OK)


@needs_ffmpeg
def test_folder_without_tools_is_skipped(tmp_path):
    assert locate(str(tmp_path)).ffmpeg == shutil.which("ffmpeg")


def test_resolve_accepts_a_file_path_and_gives_its_folder(tmp_path):
    tool = tmp_path / "ffmpeg"
    tool.write_text("")
    assert resolve_tools_dir(str(tool)) == str(tmp_path)
    assert resolve_tools_dir("   ") == ""
