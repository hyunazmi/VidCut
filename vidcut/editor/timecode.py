"""Reads a time that a person typed into the "go to time" field."""

from __future__ import annotations

import re
from typing import Optional

_NUMBER = re.compile(r"^(?:\d+(?:\.\d*)?|\.\d+)$")
_WHOLE = re.compile(r"^\d+$")
_UNITS = re.compile(r"^(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+(?:\.\d*)?|\.\d+)\s*s)?$", re.IGNORECASE)


def parse_time(text: str) -> Optional[float]:
    """Seconds for the text, or None if it is not a time.

    Accepted forms: 90, 90.5, 1:30, 1:30.5, 100:30, 01:02:03.250, 1m30s, 1h2m3s, 45s.
    Commas work as decimal points. Negative values and anything else give None.
    """
    try:
        return _parse(text)
    except (ValueError, OverflowError):  # for example a number with thousands of digits
        return None


def _parse(text: str) -> Optional[float]:
    s = text.strip().replace(",", ".")
    if not s:
        return None
    if ":" in s:
        return _parse_colons(s)
    if _NUMBER.match(s):
        return float(s)
    match = _UNITS.match(s)
    if match and any(match.groups()):
        hours, minutes, seconds = match.groups()
        return int(hours or 0) * 3600 + int(minutes or 0) * 60 + float(seconds or 0)
    return None


def _parse_colons(s: str) -> Optional[float]:
    parts = s.split(":")
    if len(parts) > 3 or not all(parts):
        return None
    *whole, seconds = parts
    if not all(_WHOLE.match(p) for p in whole) or not _NUMBER.match(seconds):
        return None
    if float(seconds) >= 60:
        return None
    if len(parts) == 3:
        hours, minutes = int(whole[0]), int(whole[1])
        if minutes >= 60:
            return None
        return hours * 3600 + minutes * 60 + float(seconds)
    return int(whole[0]) * 60 + float(seconds)  # "100:30" means 100 minutes
