"""Token statistics from Claude Code's local session logs (~/.claude/projects/**/*.jsonl).

Only Claude Code activity is visible here; chats on claude.ai or other tools never appear.
Tokens are input + output + cache creation (cache reads are left out, they would drown the rest).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .fmt import parse_iso
from .paths import claude_dir

_MODEL_RE = re.compile(r"claude-(opus|sonnet|haiku)-(\d+)(?:-(\d{1,2}))?(?!\d)")


@dataclass
class TokenStats:
    today: int = 0
    week: int = 0
    by_model: dict = field(default_factory=dict)   # last 7 days, tokens per model label
    sessions_today: int = 0

    @property
    def top_models(self) -> list:
        return sorted(self.by_model.items(), key=lambda item: item[1], reverse=True)


def short_model(name: Optional[str]) -> str:
    """'claude-sonnet-4-6-20260101' -> 'Sonnet 4.6'."""
    match = _MODEL_RE.search(name or "")
    if not match:
        return name or "?"
    family, major, minor = match.groups()
    return f"{family.title()} {major}" + (f".{minor}" if minor else "")


def _entry_tokens(usage: dict) -> int:
    return sum(int(usage.get(key) or 0) for key in
               ("input_tokens", "output_tokens", "cache_creation_input_tokens"))


def parse_log(path: Path) -> dict:
    """{message id: (timestamp, model label, tokens, session id)} for one JSONL file.

    Claude Code logs one API response over several lines that repeat the message id; the
    token counts grow, so the largest value per id wins.
    """
    found: dict = {}
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict) or entry.get("type") != "assistant":
                    continue
                message = entry.get("message")
                if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
                    continue
                moment = parse_iso(entry.get("timestamp"))
                if moment is None:
                    continue
                key = message.get("id") or entry.get("uuid") or f"{path.name}:{moment.isoformat()}"
                tokens = _entry_tokens(message["usage"])
                if key not in found or tokens > found[key][2]:
                    found[key] = (moment, short_model(message.get("model")), tokens, entry.get("sessionId"))
    except OSError:
        pass
    return found


class LocalStats:
    """Scans the logs, re-parsing only files that changed since the last scan."""

    def __init__(self, projects_dir: Optional[Path] = None):
        self.projects_dir = projects_dir or claude_dir() / "projects"
        self._cache: dict = {}

    def scan(self, now: Optional[datetime] = None) -> Optional[TokenStats]:
        """Statistics for today and the last 7 days, or None when there are no logs."""
        now = (now or datetime.now(timezone.utc)).astimezone()
        week_start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if not self.projects_dir.is_dir():
            return None

        messages: dict = {}
        live = set()
        for path in self.projects_dir.rglob("*.jsonl"):
            try:
                stat = path.stat()
            except OSError:
                continue
            if datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc) < week_start:
                continue
            live.add(path)
            cached = self._cache.get(path)
            if cached is None or cached[:2] != (stat.st_mtime, stat.st_size):
                cached = (stat.st_mtime, stat.st_size, parse_log(path))
                self._cache[path] = cached
            for key, value in cached[2].items():
                if key not in messages or value[2] > messages[key][2]:
                    messages[key] = value
        for stale in set(self._cache) - live:
            del self._cache[stale]

        stats = TokenStats()
        sessions = set()
        for moment, model, tokens, session in messages.values():
            moment = moment.astimezone()
            if moment < week_start:
                continue
            stats.week += tokens
            stats.by_model[model] = stats.by_model.get(model, 0) + tokens
            if moment >= day_start:
                stats.today += tokens
                sessions.add(session)
        stats.sessions_today = len(sessions)
        return stats if stats.week else None
