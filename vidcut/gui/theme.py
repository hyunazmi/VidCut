"""Application-wide colors and stylesheet. One neutral gray scale, one accent."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QPalette

BG = "#1f2023"
PANEL = "#17181a"
SURFACE = "#2a2c30"
SURFACE_HOVER = "#33353a"
BORDER = "#3a3c42"
TEXT = "#dcdde0"
MUTED = "#8b8d94"
DISABLED = "#5c5e65"
ACCENT = "#4d8fe8"
PLAYHEAD = "#ff5a52"

# Once a style sheet restyles a combo box or a spin box, Qt stops drawing the arrows unless an image is given
# for them. Forward slashes work in url() on every platform.
_RES = Path(__file__).resolve().parent / "resources"
ARROW_DOWN = (_RES / "arrow_down.png").as_posix()
ARROW_UP = (_RES / "arrow_up.png").as_posix()

STYLESHEET = f"""
QTabWidget::pane {{ border: none; border-top: 1px solid {BORDER}; }}
QTabBar::tab {{
    background: transparent; color: {MUTED};
    padding: 9px 20px; border: none; border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}

QToolBar {{ background: transparent; border: none; spacing: 4px; padding: 0; }}
QToolBar::separator {{ background: {BORDER}; width: 1px; margin: 6px 8px; }}
QToolBar QToolButton {{ padding: 7px; }}
QToolButton {{
    background: transparent; color: {TEXT};
    border: 1px solid transparent; border-radius: 6px; padding: 4px;
}}
QToolButton:hover {{ background: {SURFACE}; }}
QToolButton:pressed {{ background: {SURFACE_HOVER}; }}
QToolButton:checked {{ background: {SURFACE}; border-color: {BORDER}; }}
QToolButton:disabled {{ color: {DISABLED}; }}
QToolButton#transport {{ background: {SURFACE}; border: 1px solid {BORDER}; padding: 0; }}
QToolButton#transport:hover {{ background: {SURFACE_HOVER}; }}


QPushButton {{
    background: {SURFACE}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 4px; padding: 6px 16px;
}}
QPushButton:hover {{ background: {SURFACE_HOVER}; }}
QPushButton:default {{ border-color: {ACCENT}; }}
QPushButton:disabled {{ color: {DISABLED}; }}

QLineEdit, QComboBox, QSpinBox {{
    background: {PANEL}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 4px; padding: 4px 8px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QComboBox {{ padding-right: 26px; }}
QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right;
    width: 24px; border: none; border-left: 1px solid {BORDER};
    border-top-right-radius: 4px; border-bottom-right-radius: 4px;
}}
QComboBox::drop-down:hover {{ background: {SURFACE_HOVER}; }}
QComboBox::down-arrow {{ image: url("{ARROW_DOWN}"); width: 12px; height: 12px; }}
QComboBox::down-arrow:disabled {{ image: none; }}
QSpinBox {{ padding-right: 24px; }}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border; width: 20px; background: transparent;
    border: none; border-left: 1px solid {BORDER};
}}
QSpinBox::up-button {{ subcontrol-position: top right; border-top-right-radius: 4px; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; border-bottom-right-radius: 4px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {SURFACE_HOVER}; }}
QSpinBox::up-arrow {{ image: url("{ARROW_UP}"); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url("{ARROW_DOWN}"); width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{
    background: {PANEL}; color: {TEXT}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT}; selection-color: #ffffff;
}}
QTabBar {{ icon-size: 16px; }}

QStatusBar {{ background: {PANEL}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
QStatusBar::item {{ border: none; }}

QScrollArea {{ border: none; background: {PANEL}; }}
QScrollBar:horizontal {{ background: {PANEL}; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {BORDER}; border-radius: 3px; min-width: 30px; margin: 2px 0;
}}
QScrollBar::handle:horizontal:hover {{ background: {DISABLED}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

QSlider::groove:horizontal {{ height: 3px; background: {BORDER}; border-radius: 1px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 1px; }}
QSlider::handle:horizontal {{
    width: 12px; height: 12px; margin: -5px 0; background: {TEXT}; border-radius: 6px;
}}

QProgressBar {{
    background: {PANEL}; border: none; border-radius: 3px; height: 6px;
    text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}

QScrollArea#page {{ background: transparent; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#error {{ color: {PLAYHEAD}; }}
QFrame#rule {{ background: {BORDER}; border: none; max-height: 1px; }}
QLabel#dropzone {{
    background: {PANEL}; color: {MUTED};
    border: 1px dashed {BORDER}; border-radius: 6px;
}}
QLabel#dropzone[dragover="true"] {{ border-color: {ACCENT}; color: {TEXT}; }}

QMenu {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px 6px 10px; border-radius: 4px; }}
QMenu::item:selected {{ background: {ACCENT}; color: #ffffff; }}
QMenu::item:disabled {{ color: {DISABLED}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}

QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px 6px; }}
"""


def palette() -> QPalette:
    p = QPalette()
    role = QPalette.ColorRole
    p.setColor(role.Window, QColor(BG))
    p.setColor(role.WindowText, QColor(TEXT))
    p.setColor(role.Base, QColor(PANEL))
    p.setColor(role.AlternateBase, QColor(BG))
    p.setColor(role.Text, QColor(TEXT))
    p.setColor(role.Button, QColor(SURFACE))
    p.setColor(role.ButtonText, QColor(TEXT))
    p.setColor(role.ToolTipBase, QColor(SURFACE))
    p.setColor(role.ToolTipText, QColor(TEXT))
    p.setColor(role.Highlight, QColor(ACCENT))
    p.setColor(role.HighlightedText, QColor("#ffffff"))
    p.setColor(role.PlaceholderText, QColor(MUTED))
    p.setColor(role.Link, QColor(ACCENT))
    return p


def apply(app) -> None:
    app.setStyle("Fusion")
    app.setPalette(palette())
    app.setStyleSheet(STYLESHEET)
