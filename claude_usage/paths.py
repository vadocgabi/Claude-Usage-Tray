"""Filesystem locations. The installed exe keeps its data in %APPDATA%, source runs next to the script."""
from __future__ import annotations

import os
import sys
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    BASE = Path(os.environ.get("APPDATA", Path.home())) / "ClaudeUsageTray"
else:
    BASE = Path(__file__).resolve().parent.parent
BASE.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = BASE / "config.json"      # credentials + auth mode (secrets encrypted)
SETTINGS_PATH = BASE / "settings.json"  # preferences chosen from the tray menu
LOG_PATH = BASE / "claude_usage_tray.log"


def claude_dir() -> Path:
    """Claude Code's config directory (honours CLAUDE_CONFIG_DIR)."""
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
