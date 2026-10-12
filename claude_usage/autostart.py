"""Start with the desktop session (registry on Windows, an XDG autostart entry on Linux)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from . import system
from .paths import FROZEN


def command() -> str:
    """Command line that starts this application."""
    appimage = os.environ.get("APPIMAGE")
    if appimage:                      # the mounted AppImage path changes on every run, the file does not
        return f'"{appimage}"'
    if FROZEN:
        return f'"{sys.executable}"'
    if system.NAME == "windows":
        interpreter = Path(sys.executable).with_name("pythonw.exe")
    else:
        interpreter = Path(sys.executable)
    return f'"{interpreter}" "{Path(sys.argv[0]).resolve()}"'


def is_enabled() -> bool:
    return system.autostart_enabled()


def set_enabled(enable: bool) -> None:
    system.set_autostart(enable, command())
