"""The icon set, as SVG. No Qt import here, so the icons can be checked and previewed anywhere.

All icons are drawn on a 24 x 24 grid in one style: 2 px strokes, round caps and joins, no fill
(play, pause and the small marks inside a few icons are filled). The shapes use only line,
polyline, polygon, circle and rect, which keeps every icon easy to read and edit.
Colors are not part of the icons: "currentColor" is replaced when an icon is rendered, so the
theme decides the color.
"""

from __future__ import annotations

from typing import Dict

_SPEAKER = '<polygon points="4,9 8,9 13,5 13,19 8,15 4,15"/>'

ICONS: Dict[str, str] = {
    "folder": '<rect x="3" y="8" width="18" height="11" rx="2"/><polyline points="3,10 3,6 4,5 8.5,5 10.5,8"/>',
    "scissors": (
        '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>'
        '<line x1="20" y1="4" x2="8.1" y2="15.9"/><line x1="14.5" y1="14.5" x2="20" y2="20"/>'
        '<line x1="8.1" y1="8.1" x2="12" y2="12"/>'
    ),
    "trash": (
        '<line x1="4" y1="7" x2="20" y2="7"/><polyline points="9,7 9,4 15,4 15,7"/>'
        '<polygon points="6,7 7,20 17,20 18,7"/>'
        '<line x1="10" y1="11" x2="10" y2="16"/><line x1="14" y1="11" x2="14" y2="16"/>'
    ),
    "undo": (
        '<polyline points="8,4 4,8 8,12"/><polyline points="4,8 13,8 16,8.8 18.2,11 19,14 18.2,17 16,19.2 13,20 8,20"/>'
    ),
    "redo": (
        '<polyline points="16,4 20,8 16,12"/><polyline points="20,8 11,8 8,8.8 5.8,11 5,14 5.8,17 8,19.2 11,20 16,20"/>'
    ),
    "export": (
        '<polyline points="4,15 4,20 20,20 20,15"/><line x1="12" y1="15" x2="12" y2="4"/>'
        '<polyline points="7,9 12,4 17,9"/>'
    ),
    "play": '<polygon points="8,5 19,12 8,19" fill="currentColor" stroke-width="1.5"/>',
    "pause": (
        '<rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none"/>'
        '<rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none"/>'
    ),
    "volume": _SPEAKER + '<polyline points="16.5,9 18,12 16.5,15"/><polyline points="19,6.5 21.5,12 19,17.5"/>',
    "volume_off": _SPEAKER + '<line x1="16" y1="9" x2="21" y2="15"/><line x1="21" y1="9" x2="16" y2="15"/>',
    "waveform": (
        '<line x1="4" y1="10" x2="4" y2="14"/><line x1="8" y1="6" x2="8" y2="18"/>'
        '<line x1="12" y1="3" x2="12" y2="21"/><line x1="16" y1="7" x2="16" y2="17"/>'
        '<line x1="20" y1="10" x2="20" y2="14"/>'
    ),
    "film": (
        '<rect x="3" y="5" width="18" height="14" rx="2"/>'
        '<polygon points="10,9 10,15 15,12" fill="currentColor" stroke-width="1"/>'
    ),
    "keyboard": (
        '<rect x="2" y="6" width="20" height="12" rx="2"/>'
        '<line x1="6" y1="10" x2="6.01" y2="10"/><line x1="10" y1="10" x2="10.01" y2="10"/>'
        '<line x1="14" y1="10" x2="14.01" y2="10"/><line x1="18" y1="10" x2="18.01" y2="10"/>'
        '<line x1="8" y1="14" x2="16" y2="14"/>'
    ),
    "sliders": (
        '<line x1="4" y1="6" x2="7" y2="6"/><circle cx="9" cy="6" r="2"/><line x1="11" y1="6" x2="20" y2="6"/>'
        '<line x1="4" y1="12" x2="13" y2="12"/><circle cx="15" cy="12" r="2"/><line x1="17" y1="12" x2="20" y2="12"/>'
        '<line x1="4" y1="18" x2="6" y2="18"/><circle cx="8" cy="18" r="2"/><line x1="10" y1="18" x2="20" y2="18"/>'
    ),
    "info": (
        '<circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="17"/>'
        '<line x1="12" y1="7.5" x2="12.01" y2="7.5"/>'
    ),
    "clock": '<circle cx="12" cy="12" r="9"/><polyline points="12,7 12,12 15,14"/>',
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "arrow_left": '<line x1="19" y1="12" x2="5" y2="12"/><polyline points="11,6 5,12 11,18"/>',
    "arrow_right": '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="13,6 19,12 13,18"/>',
    "close": '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
}

_ROOT = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
    'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    "{body}</svg>"
)


def svg_document(name: str, color: str, size: int = 24) -> str:
    """The complete SVG text of an icon in one color, for example svg_document("cut", "#dcdde0")."""
    return _ROOT.format(size=size, color=color, body=ICONS[name].replace("currentColor", color))
