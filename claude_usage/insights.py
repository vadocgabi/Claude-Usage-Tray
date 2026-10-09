"""Derived information: pace, limit forecast and re-armed alerts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from .fmt import parse_iso
from .model import Limit, Usage

MIN_ELAPSED = timedelta(minutes=10)   # too little history to extrapolate before this
FORECAST_MIN_PCT = 20                 # do not predict from a handful of percent
HYSTERESIS = 5                        # usage must fall this far below a threshold to re-arm it


def _window(limit: Limit, now: datetime) -> Optional[tuple]:
    """(elapsed, window length) of the limit's current window, or None when unknown."""
    resets = parse_iso(limit.resets_at)
    if resets is None or not limit.window_hours:
        return None
    length = timedelta(hours=limit.window_hours)
    elapsed = now - (resets - length)
    return max(timedelta(0), min(elapsed, length)), length


def pace_pct(limit: Limit, now: Optional[datetime] = None) -> Optional[float]:
    """Share of the window that has elapsed (0-100): the 'on pace' usage level."""
    found = _window(limit, now or datetime.now(timezone.utc))
    return None if found is None else 100 * found[0] / found[1]


def seconds_to_limit(limit: Limit, now: Optional[datetime] = None) -> Optional[float]:
    """Seconds until 100% at the current burn rate, or None if it will not be reached before the reset."""
    now = now or datetime.now(timezone.utc)
    if limit.pct >= 100:
        return 0.0
    found = _window(limit, now)
    if found is None or limit.pct < FORECAST_MIN_PCT or found[0] < MIN_ELAPSED:
        return None
    elapsed, length = found
    rate = limit.pct / elapsed.total_seconds()          # percent per second
    remaining = (100 - limit.pct) / rate
    return remaining if remaining < (length - elapsed).total_seconds() else None


@dataclass
class Alert:
    kind: str                 # 'threshold', 'forecast' or 'reset'
    limit: Limit
    value: float = 0.0        # threshold percent (threshold) or seconds (forecast)


class AlertTracker:
    """Decides which notifications are due; each fires once per window and re-arms on reset."""

    def __init__(self, thresholds: tuple = (80, 90, 100)):
        self.thresholds = sorted(thresholds)
        self._state: dict = {}

    def check(self, usage: Usage, now: Optional[datetime] = None) -> list:
        now = now or datetime.now(timezone.utc)
        alerts = []
        for limit in (usage.session, usage.weekly):
            if limit is not None:
                alerts += self._check_limit(limit, now)
        return alerts

    def _check_limit(self, limit: Limit, now: datetime) -> list:
        state = self._state.setdefault(limit.key, {"resets": limit.resets_at, "armed": set(),
                                                   "peak": 0.0, "forecast": False, "seeded": False})
        alerts = []
        if state["resets"] != limit.resets_at:  # a new window started
            if state["peak"] >= self.thresholds[0] and limit.pct < self.thresholds[0]:
                alerts.append(Alert("reset", limit))
            state.update(resets=limit.resets_at, armed=set(), peak=0.0, forecast=False)
        state["peak"] = max(state["peak"], limit.pct)

        for threshold in self.thresholds:
            if limit.pct < threshold - HYSTERESIS:
                state["armed"].discard(threshold)
        crossed = [t for t in self.thresholds if limit.pct >= t and t not in state["armed"]]
        if crossed:
            state["armed"].update(t for t in self.thresholds if limit.pct >= t)
            if state["seeded"]:  # the first reading only seeds the state, no alert at startup
                alerts.append(Alert("threshold", limit, max(crossed)))
        state["seeded"] = True

        eta = seconds_to_limit(limit, now)
        if eta is not None and eta > 0 and not state["forecast"] and state["armed"] != set(self.thresholds):
            state["forecast"] = True
            alerts.append(Alert("forecast", limit, eta))
        return alerts


def poll_delay(interval: float, usage: Optional[Usage], now: datetime, backoff: float = 0,
               jitter: float = 0, min_delay: float = 15) -> float:
    """Seconds to wait before the next fetch: the interval plus jitter, stretched by a rate-limit
    back-off, but shortened to land just after an imminent window reset."""
    delay = max(interval + jitter, backoff)
    if usage is not None and backoff <= 0:
        for limit in usage.limits():
            resets = parse_iso(limit.resets_at)
            if resets is not None:
                until = (resets - now).total_seconds() + 5
                if 0 < until < delay:
                    delay = until
    return max(min_delay, delay)
