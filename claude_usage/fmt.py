"""Small formatting helpers for times, durations and token counts."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def parse_iso(value: Optional[str]) -> Optional[datetime]:
    """ISO 8601 timestamp -> aware datetime, or None when missing or malformed."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def local_time(value: Optional[str], with_day: bool, days: list) -> str:
    moment = parse_iso(value)
    if moment is None:
        return "?"
    moment = moment.astimezone()
    return f"{days[moment.weekday()]} {moment:%H:%M}" if with_day else f"{moment:%H:%M}"


def duration(seconds: float, units: tuple = ("d", "h", "m")) -> str:
    """Compact duration such as '2d 3h', '4h 05m' or '12m'; `units` are the d/h/m suffixes."""
    day, hour, minute = units
    minutes = max(0, int(seconds // 60))
    days, rest = divmod(minutes, 1440)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days}{day} {hours}{hour}"
    if hours:
        return f"{hours}{hour} {mins:02d}{minute}"
    return f"{mins}{minute}"


def tokens(count: int) -> str:
    """1_250_000 -> '1.25M', 48_000 -> '48.0K'."""
    for size, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if count >= size:
            return f"{count / size:.2f}{suffix}" if size > 1_000 else f"{count / size:.1f}{suffix}"
    return str(count)
