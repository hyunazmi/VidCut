from __future__ import annotations

import os
import sys
from typing import List, Optional

# Qt logging rules that hide harmless noise. Set VIDCUT_QT_LOGS=1 to keep all Qt logs.
_QUIET_RULES = (
    "qt.qpa.wayland.textinput=false",  # known Qt/Wayland focus warning, no effect
    "qt.multimedia.ffmpeg*.debug=false",  # media dump printed by Qt's media backend
    "qt.multimedia.ffmpeg*.info=false",
)


def _quiet_qt_logs() -> None:
    if os.environ.get("VIDCUT_QT_LOGS"):
        return
    # Qt applies later rules last, so ours override a broad "*.debug=true" set elsewhere.
    existing = os.environ.get("QT_LOGGING_RULES", "").strip(";")
    rules = ";".join(_QUIET_RULES)
    os.environ["QT_LOGGING_RULES"] = f"{existing};{rules}" if existing else rules
    os.environ.pop("QT_FFMPEG_DEBUG", None)  # makes Qt's FFmpeg backend print verbose logs


def main(argv: Optional[List[str]] = None) -> int:
    _quiet_qt_logs()
    try:
        from PySide6.QtWidgets import QApplication  # noqa: PLC0415 - checked here, so a missing PySide6 gets a message
    except ImportError:
        print("PySide6 is not installed. Run:  pip install PySide6", file=sys.stderr)
        return 2
    from . import app_icon, theme  # noqa: PLC0415 - imported after the PySide6 check above
    from .main_window import MainWindow  # noqa: PLC0415

    argv = list(sys.argv if argv is None else argv)
    app = QApplication(argv)
    app.setApplicationName("VidCut")
    if sys.platform.startswith("linux"):
        app.setDesktopFileName("vidcut")  # the name Linux desktops use to find the window icon
    app.setWindowIcon(app_icon.load_app_icon())
    theme.apply(app)
    window = MainWindow(argv[1] if len(argv) > 1 else "")
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
