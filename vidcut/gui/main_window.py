"""The main window: the Editor and About tabs, the actions (keyboard shortcuts and toolbar) and the wiring."""

from __future__ import annotations

import os
from typing import Dict

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMainWindow, QTabWidget, QToolBar, QVBoxLayout, QWidget

from .. import appinfo
from ..core.formats import VIDEO_EXTS
from . import icons, settings
from .about import AboutPage
from .drop_filter import VideoDropFilter
from .editor_page import EditorPage
from .export_flow import ExportController
from .settings_panel import SettingsPanel
from .shortcuts import GLOBAL_IDS, SHORTCUTS, button_text, by_id

VIDEO_FILTER = "Video files (" + " ".join(f"*.{e}" for e in VIDEO_EXTS) + ");;All files (*)"
EDITOR_TAB, SETTINGS_TAB, ABOUT_TAB = range(3)

# The toolbar shows icons only, in this order. The names are the icons of icon_svgs.py.
TOOLBAR = (
    ("open", "folder"),
    ("cut", "scissors"),
    ("delete", "trash"),
    ("undo", "undo"),
    ("redo", "redo"),
    ("export", "export"),
)
TOOLBAR_ICON_SIZE = 20


class MainWindow(QMainWindow):
    def __init__(self, initial_file: str = "") -> None:
        super().__init__()
        self.setWindowTitle(appinfo.NAME)
        self.resize(1180, 780)
        self.setMinimumSize(900, 580)
        self._exporting = False  # True from the start of an export until the user closes its popup

        self.editor = EditorPage(settings.locate_tools)
        self.editor.message.connect(self._show_message)
        self.editor.state_changed.connect(self._refresh_actions)
        self.editor.video_opened.connect(self._on_video_opened)
        self.settings_page = SettingsPanel()
        self.settings_page.ffmpeg_changed.connect(self._on_ffmpeg_changed)

        # The export has no window of its own: it opens a popup that shows its progress.
        self.exporter = ExportController(self, settings.locate_tools)
        self.exporter.started.connect(self._on_export_started)
        self.exporter.finished.connect(self._on_export_finished)
        self.exporter.closed.connect(self._on_export_closed)

        self.about_page = AboutPage(settings.locate_tools)

        self.action_map = self._build_actions()
        self.tabs = self._build_tabs()
        self.setCentralWidget(self.tabs)

        self.drop_filter = VideoDropFilter(self)
        self.drop_filter.hover_changed.connect(self.editor.set_drop_highlight)
        # One dropped video opens the project (asking first when edits would be lost).
        self.drop_filter.videos_dropped.connect(lambda paths: self.open_video(paths[0], confirm_replace=True))
        self.drop_filter.rejected.connect(lambda: self._show_message("That file type is not supported.", 4000))
        self.drop_filter.attach(self)

        self._show_message("Open a video to start.", 0)
        self._refresh_actions()
        if initial_file:
            self.open_video(initial_file)

    # ================= construction =================
    def _build_actions(self) -> Dict[str, QAction]:
        """One QAction per entry of shortcuts.SHORTCUTS."""
        editor = self.editor
        handlers = {
            "open": self.choose_file,
            "export": self.export,
            "play": editor.toggle_play,
            "cut": editor.cut,
            "delete": editor.delete_current,
            "undo": editor.undo,
            "redo": editor.redo,
            "step_back": lambda: editor.step_frames(-1),
            "step_forward": lambda: editor.step_frames(1),
            "far_back": lambda: editor.step_far(-1),
            "far_forward": lambda: editor.step_far(1),
            "jump_back": lambda: editor.step_seconds(-1),
            "jump_forward": lambda: editor.step_seconds(1),
            "prev_cut": lambda: editor.jump_cut(-1),
            "next_cut": lambda: editor.jump_cut(1),
            "go_start": editor.go_start,
            "go_end": editor.go_end,
            "go_to_time": editor.focus_time_field,
            "zoom_in": editor.zoom_in,
            "zoom_out": editor.zoom_out,
            "zoom_fit": editor.zoom_fit,
        }
        if set(handlers) != set(by_id()):
            raise RuntimeError("shortcuts.SHORTCUTS and the handlers in MainWindow are out of sync")

        toolbar_icons = dict(TOOLBAR)
        actions: Dict[str, QAction] = {}
        for shortcut in SHORTCUTS:
            action = QAction(shortcut.label, self)
            if shortcut.id in toolbar_icons:
                action.setIcon(icons.icon(toolbar_icons[shortcut.id]))
            action.setShortcuts([QKeySequence(key) for key in shortcut.keys])
            action.setToolTip(button_text(shortcut))  # icon-only buttons: the tooltip says what and which key
            action.setStatusTip(shortcut.tip)
            action.triggered.connect(handlers[shortcut.id])
            self.addAction(action)  # works anywhere in the window, not only through the toolbar
            actions[shortcut.id] = action
        return actions

    def _build_toolbar(self) -> QToolBar:
        """One row of icons. Hover a button to see its name and shortcut."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        toolbar.setIconSize(QSize(TOOLBAR_ICON_SIZE, TOOLBAR_ICON_SIZE))
        for shortcut_id, _icon in TOOLBAR:
            toolbar.addAction(self.action_map[shortcut_id])
        return toolbar

    def _build_tabs(self) -> QTabWidget:
        editor_tab = QWidget()
        layout = QVBoxLayout(editor_tab)
        layout.setContentsMargins(12, 8, 12, 10)
        layout.setSpacing(10)
        layout.addWidget(self._build_toolbar())
        layout.addWidget(self.editor, 1)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tabs.tabBar().setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tabs.addTab(editor_tab, icons.icon("film"), "Editor")
        tabs.addTab(self.settings_page, icons.icon("sliders"), "Settings")
        tabs.addTab(self.about_page, icons.icon("info"), "About")
        tabs.currentChanged.connect(self._on_tab_changed)
        return tabs

    # ================= opening and exporting =================
    def choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open video", "", VIDEO_FILTER)
        if path:
            self.open_video(path)

    def open_video(self, path: str, confirm_replace: bool = False) -> None:
        if not self._exporting:
            self.editor.open_video(path, confirm_replace)

    def export(self) -> None:
        if self._exporting:
            return
        self.editor.pause()
        self.exporter.start(self.editor.export_request())

    # ================= the export, shown in a popup =================
    def _on_export_started(self) -> None:
        self._set_export_mode(True)

    def _on_export_finished(self, kind: str, text: str) -> None:
        if kind == "cancel":
            self._show_message("Export cancelled.", 4000)

    def _on_export_closed(self, kind: str) -> None:
        """The user closed the export popup: back to editing."""
        self._set_export_mode(False)
        if kind == "ok":
            self._show_message(f"Saved {os.path.basename(self.exporter.last_output)}", 6000)

    def _set_export_mode(self, exporting: bool) -> None:
        """While exporting, the editing shortcuts are off."""
        self._exporting = exporting
        self._refresh_actions()

    # ================= reacting to the pages =================
    def _show_message(self, text: str, timeout_ms: int) -> None:
        self.statusBar().showMessage(text, timeout_ms)

    def _on_video_opened(self, path: str) -> None:
        self.setWindowTitle(f"{os.path.basename(path)} - {appinfo.NAME}")
        self.tabs.setCurrentIndex(EDITOR_TAB)

    def _on_ffmpeg_changed(self) -> None:
        self.about_page.invalidate()
        self._show_message("FFmpeg location updated.", 4000)

    def _on_tab_changed(self, index: int) -> None:
        if index != EDITOR_TAB:
            self.editor.pause()
        if index == SETTINGS_TAB:
            self.settings_page.refresh()
        elif index == ABOUT_TAB:
            self.about_page.refresh()
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        """Editing shortcuts only work on the Editor tab with a video loaded, and never during an export."""
        usable = self.tabs.currentIndex() == EDITOR_TAB and self.editor.has_video and not self._exporting
        for shortcut_id, action in self.action_map.items():
            action.setEnabled(not self._exporting and (shortcut_id in GLOBAL_IDS or usable))
        self.action_map["undo"].setEnabled(usable and self.editor.can_undo)
        self.action_map["redo"].setEnabled(usable and self.editor.can_redo)

    def closeEvent(self, event) -> None:
        self.exporter.shutdown()
        self.editor.shutdown()
        super().closeEvent(event)
