"""Filesystem locations.

An installed or packaged build keeps its data in the per-user config folder of the platform
(%APPDATA% on Windows, ~/.config on Linux); a source checkout keeps it next to the code.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import system

FROZEN = getattr(sys, "frozen", False)
SOURCE_DIR = Path(__file__).resolve().parent.parent


def _is_source_checkout() -> bool:
    return (SOURCE_DIR / "claude_usage_tray.py").is_file() and os.access(SOURCE_DIR, os.W_OK)


BASE = SOURCE_DIR if (not FROZEN and _is_source_checkout()) else system.data_dir()
BASE.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = BASE / "config.json"      # credentials + auth mode (secrets protected)
SETTINGS_PATH = BASE / "settings.json"  # preferences chosen from the tray menu
LOG_PATH = BASE / "claude_usage_tray.log"


def claude_dir() -> Path:
    """Claude Code's config directory (honours CLAUDE_CONFIG_DIR)."""
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
