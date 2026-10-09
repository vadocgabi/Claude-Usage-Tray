"""Manual update check against the GitHub releases of this project (runs only when the user asks)."""
from __future__ import annotations

import json
import re
import urllib.request
from typing import Optional

from . import REPO_URL, __version__

API_URL = "https://api.github.com/repos/vadocgabi/claude.ai_usage_systemtray/releases/latest"
RELEASES_URL = REPO_URL + "/releases/latest"


def version_tuple(text: str) -> tuple:
    return tuple(int(part) for part in re.findall(r"\d+", text)[:3])


def is_newer(candidate: str, current: str = __version__) -> bool:
    return version_tuple(candidate) > version_tuple(current)


def latest_version() -> Optional[str]:
    """Latest released version string, or None if the check fails."""
    request = urllib.request.Request(API_URL, headers={"Accept": "application/vnd.github+json",
                                                       "User-Agent": f"claude-usage-tray/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return str(json.loads(response.read(200_000)).get("tag_name", "")).lstrip("v") or None
    except (OSError, ValueError):
        return None
