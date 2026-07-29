"""Timecode conversion helpers."""

from __future__ import annotations

import re

_TIMECODE_RE = re.compile(
    r"^(?:(?P<hours>\d{1,2}):)?(?P<minutes>\d{1,2}):(?P<seconds>\d{1,2})(?:\.(?P<millis>\d{1,3}))?$"
)


def format_timecode(milliseconds: int, *, include_ms: bool = False) -> str:
    if milliseconds < 0:
        raise ValueError("milliseconds must be non-negative")

    total_seconds, millis = divmod(milliseconds, 1000)
    minutes_total, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes_total, 60)
    if include_ms:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def parse_timecode(value: str) -> int:
    match = _TIMECODE_RE.match(value.strip())
    if not match:
        raise ValueError(f"Invalid timecode: {value!r}")

    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    millis_text = match.group("millis") or "0"
    millis = int(millis_text.ljust(3, "0"))

    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"Invalid timecode: {value!r}")

    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis

