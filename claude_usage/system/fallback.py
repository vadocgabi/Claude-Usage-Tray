"""Other platforms (macOS, BSD): conservative defaults so the application at least starts.

Behaviour is Linux-like where it can be (XDG folders, plain 0600 config) and everything that needs
a native API is a no-op. A proper macOS implementation (Keychain, LaunchAgent) can replace this file.
"""
from __future__ import annotations

import os
from pathlib import Path

NAME = "fallback"
FLYOUT_BORDERLESS = False


def data_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "ClaudeUsageTray"


def protect(name: str, value: str) -> str:
    return value or ""


def unprotect(stored: str) -> str:
    return "" if (stored or "").startswith(("dpapi:", "keyring:")) else (stored or "")


def native_credentials() -> str:
    return ""


def autostart_enabled() -> bool:
    return False


def set_autostart(enable: bool, command: str) -> None:
    raise OSError("autostart is not supported on this platform")


def acquire_single_instance() -> bool:
    return True


def system_language() -> str:
    value = (os.environ.get("LANG") or "").lower()
    return "hu" if value.startswith("hu") else "en"


def prefers_dark() -> bool:
    return False


def style_window(window, dark: bool) -> None:
    pass


def work_area(window=None) -> tuple:
    if window is not None:
        return 0, 0, window.winfo_screenwidth(), window.winfo_screenheight()
    return 0, 0, 1280, 720
