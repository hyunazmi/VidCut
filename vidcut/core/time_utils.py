from __future__ import annotations

import math


def format_time(seconds: float) -> str:
    ms = int(math.floor(max(0.0, seconds) * 1000.0 + 0.5))
    h, rest = divmod(ms, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, milli = divmod(rest, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{milli:03d}"


def format_fixed(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}"


def format_seconds(seconds: float) -> str:
    return format_fixed(seconds, 6)


def format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    units = ("KB", "MB", "GB")
    n = num_bytes / 1024.0
    u = 0
    while n >= 1024.0 and u < len(units) - 1:
        n /= 1024.0
        u += 1
    return f"{format_fixed(n, 1)} {units[u]}"


def format_eta(seconds: float) -> str:
    """Remaining time as MM:SS (or H:MM:SS); '--:--' when unknown (negative)."""
    if seconds < 0:
        return "--:--"
    total = int(seconds + 0.5)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:d}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"
