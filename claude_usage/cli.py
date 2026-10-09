"""Command line entry point: `--autostart`, `--no-autostart`, `--version`, otherwise run the tray app."""
from __future__ import annotations

import ctypes
import logging
import sys
from logging.handlers import RotatingFileHandler

from . import APP_NAME, __version__
from .paths import LOG_PATH

ERROR_ALREADY_EXISTS = 183
_mutex = None  # keeps the single-instance mutex alive for the whole process


def already_running() -> bool:
    global _mutex
    try:
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, f"Local\\{APP_NAME}_SingleInstance")
        return ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS
    except (OSError, AttributeError):
        return False


def setup_logging() -> None:
    """File log without secrets: only message keys, HTTP codes and stack traces are written."""
    handler = RotatingFileHandler(LOG_PATH, maxBytes=200_000, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger("claude_usage").addHandler(handler)
    logging.getLogger("claude_usage").setLevel(logging.INFO)


def main(argv: list) -> int:
    if "--version" in argv:
        print(f"Claude Usage Tray {__version__}")
        return 0
    if "--autostart" in argv or "--no-autostart" in argv:
        from . import autostart
        from .config import load_config
        from .i18n import resolve_language, tr
        enable = "--autostart" in argv
        autostart.set_enabled(enable)
        print(tr(resolve_language(load_config()["language"]), "autostart_on" if enable else "autostart_off"))
        return 0
    if already_running():
        return 0
    setup_logging()
    from .app import App
    App().run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
