"""The application icon, loaded from vidcut/gui/resources/."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
APP_ICON_NAME = "vidcut.png"


def load_app_icon() -> QIcon:
    return QIcon(str(RESOURCES_DIR / APP_ICON_NAME))
