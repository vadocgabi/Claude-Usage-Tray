"""Command line entry point: `--autostart`, `--no-autostart`, `--version`, otherwise run the tray app."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from . import __version__, system
from .paths import LOG_PATH



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
    if "--diagnose" in argv:
        from . import diagnose
        out = argv[argv.index("--out") + 1] if "--out" in argv and argv.index("--out") + 1 < len(argv) else ""
        return diagnose.run(out)
    if "--autostart" in argv or "--no-autostart" in argv:
        from . import autostart
        from .config import load_config
        from .i18n import resolve_language, tr
        enable = "--autostart" in argv
        autostart.set_enabled(enable)
        print(tr(resolve_language(load_config()["language"]), "autostart_on" if enable else "autostart_off"))
        return 0
    if not system.acquire_single_instance():
        return 0
    setup_logging()
    from .app import App
    App().run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
