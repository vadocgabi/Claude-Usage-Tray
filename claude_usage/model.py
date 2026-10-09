"""Plain data containers shared by the data sources, the logic and the UI."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

SESSION_HOURS = 5
WEEK_HOURS = 7 * 24


@dataclass
class Limit:
    """One usage window. `key` is 'session', 'weekly', 'extra' or 'model:<name>'."""
    key: str
    label: str            # display name for models, empty for built-in windows (translated by the UI)
    pct: float
    resets_at: Optional[str] = None  # ISO 8601 timestamp
    window_hours: Optional[float] = None


@dataclass
class Usage:
    session: Optional[Limit] = None
    weekly: Optional[Limit] = None
    models: list = field(default_factory=list)      # per-model weekly limits (Sonnet, Opus, ...)
    extra: Optional[Limit] = None                   # extra / overage usage
    breakdown: list = field(default_factory=list)   # [(name, pct)] share of weekly usage per product
    plan: str = ""
    source: str = ""                                # 'oauth' or 'cookie'

    def limits(self) -> list:
        """All windows in display order."""
        found = [self.session, self.weekly, *self.models, self.extra]
        return [limit for limit in found if limit is not None]


@dataclass
class Snapshot:
    """Everything the UI shows. `usage` keeps the last good value while `error` describes the latest failure."""
    usage: Optional[Usage] = None
    stats: object = None                 # localstats.TokenStats or None
    updated: object = None               # datetime of the last successful fetch
    error: Optional[tuple] = None        # (message key, argument)

    @property
    def stale(self) -> bool:
        return self.usage is not None and self.error is not None
