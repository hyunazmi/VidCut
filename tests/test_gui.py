"""Window-level checks, run offscreen. Audio is stubbed because the test machine may have no sound device."""

import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
PySide6 = pytest.importorskip("PySide6")

import vidcut.gui.playback as playback  # noqa: E402

playback.create_audio_output = lambda parent: (None, "no audio device in tests")

from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from vidcut.gui import export_flow, theme  # noqa: E402
from vidcut.gui.export_progress import ExportProgress  # noqa: E402
from vidcut.gui.main_window import MainWindow  # noqa: E402
from vidcut.gui.shortcuts import SHORTCUTS  # noqa: E402


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    theme.apply(application)
    return application


def _wait(app, predicate, timeout=60.0):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_tabs_and_shortcuts(app):
    window = MainWindow()
    try:
        assert [window.tabs.tabText(i) for i in range(3)] == ["Editor", "Settings", "About"]
        assert set(window.action_map) == {s.id for s in SHORTCUTS}
        assert "add_clip" not in window.action_map
    finally:
        window.close()


def test_cut_delete_undo_redo(app, sample_video):
    window = MainWindow()
    try:
        window.resize(1180, 780)
        window.show()
        editor = window.editor
        window.open_video(sample_video)
        QTest.qWait(100)
        editor.seek_timeline(5.0)
        window.action_map["cut"].trigger()
        editor.seek_timeline(12.0)
        window.action_map["cut"].trigger()
        assert len(editor.model.clips) == 3
        editor.seek_timeline(6.0)
        window.action_map["delete"].trigger()
        assert abs(editor.model.total - 13.0) < 1e-6
        window.action_map["undo"].trigger()
        assert abs(editor.model.total - 20.0) < 1e-6
        window.action_map["redo"].trigger()
        assert abs(editor.model.total - 13.0) < 1e-6
    finally:
        window.close()


def test_export_popup_reports_result(app, sample_video, out_dir, monkeypatch):
    class FakeDialog:
        def __init__(self, parent, default_path):
            self._path = os.path.join(out_dir, "result.mp4")

        def exec(self):
            from PySide6.QtWidgets import QDialog

            return QDialog.DialogCode.Accepted

        def output_path(self):
            return self._path

    monkeypatch.setattr(export_flow, "ExportDialog", FakeDialog)
    window = MainWindow()
    try:
        window.open_video(sample_video)
        model = window.editor.model
        model.split(5.0)
        model.split(12.0)
        model.delete(1)  # two separate parts: 0-5 and 12-20
        window.action_map["export"].trigger()
        assert _wait(app, lambda: isinstance(window.exporter._popup, ExportProgress))
        popup = window.exporter._popup
        assert popup.isModal() and not window.action_map["cut"].isEnabled()
        assert _wait(app, lambda: popup.done_button.isVisible(), 120)
        assert popup.title.text() == "Export finished"
        assert popup.counter.text() == "2 / 2"
        popup.done_button.click()
        assert _wait(app, lambda: window.exporter._popup is None, 10)
        assert os.path.isfile(os.path.join(out_dir, "result.mp4"))
        assert window.action_map["cut"].isEnabled()
    finally:
        window.close()
