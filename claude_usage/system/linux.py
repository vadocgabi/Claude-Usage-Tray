"""Linux: XDG directories, Secret Service keyring, .desktop autostart, flock single instance,
desktop colour-scheme and work-area detection that work on X11 and Wayland (via XWayland)."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

NAME = "linux"
FLYOUT_BORDERLESS = False   # window managers differ too much for a borderless focus-closing popup
APP_DIR = "ClaudeUsageTray"
KEYRING_SERVICE = "ClaudeUsageTray"
KEYRING_PREFIX = "keyring:"
_lock_file = None           # keeps the single-instance lock alive for the whole process


def _home() -> Path:
    return Path(os.environ.get("HOME") or Path.home())


def data_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else _home() / ".config") / APP_DIR


def _run(command: list, timeout: float = 2.0) -> str:
    """Stdout of a short helper command, or '' when it is missing, fails or hangs."""
    if shutil.which(command[0]) is None:
        return ""
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return done.stdout if done.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


# ---------------------------------------------------------------- secrets
def _keyring():
    """The `keyring` module when a real backend (Secret Service / KWallet) is usable, else None."""
    try:
        import keyring
        backend = keyring.get_keyring()
        if getattr(backend, "priority", 0) < 1:
            return None
        return keyring
    except Exception:
        return None


def protect(name: str, value: str) -> str:
    """Stores the secret in the desktop keyring; without one the plain value goes into the
    owner-only (0600) config file, the same protection Claude Code gives its own credentials."""
    if not value:
        return ""
    keyring = _keyring()
    if keyring is not None:
        try:
            keyring.set_password(KEYRING_SERVICE, name, value)
            return KEYRING_PREFIX + name
        except Exception:
            pass
    return value


def unprotect(stored: str) -> str:
    if not stored:
        return ""
    if stored.startswith(KEYRING_PREFIX):
        keyring = _keyring()
        if keyring is None:
            return ""
        try:
            return keyring.get_password(KEYRING_SERVICE, stored[len(KEYRING_PREFIX):]) or ""
        except Exception:
            return ""
    if stored.startswith("dpapi:"):   # config copied from a Windows machine: cannot be decrypted here
        return ""
    return stored


def native_credentials() -> str:
    return ""   # Claude Code keeps its login in ~/.claude/.credentials.json on Linux


# ---------------------------------------------------------------- autostart
def _autostart_file() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else _home() / ".config") / "autostart" / f"{APP_DIR}.desktop"


def autostart_enabled() -> bool:
    return _autostart_file().is_file()


def set_autostart(enable: bool, command: str) -> None:
    path = _autostart_file()
    if not enable:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Claude Usage Tray\n"
        "Comment=Shows your claude.ai session and weekly usage limits\n"
        f"Exec={command}\n"
        "Icon=claude-usage-tray\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        "X-GNOME-Autostart-enabled=true\n", encoding="utf-8")


# ---------------------------------------------------------------- process / session
def acquire_single_instance() -> bool:
    """Exclusive advisory lock on a per-user file; released automatically when the process exits."""
    global _lock_file
    try:
        import fcntl
        folder = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        path = Path(folder) / f"claude-usage-tray-{os.getuid()}.lock"
        handle = open(path, "a+")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        _lock_file = handle
        return True
    except (ImportError, OSError):
        return True


def system_language() -> str:
    for variable in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = (os.environ.get(variable) or "").lower()
        if value and value not in ("c", "posix"):
            return "hu" if value.startswith("hu") else "en"
    return "en"


# ---------------------------------------------------------------- appearance
_dark_cache: Optional[bool] = None


def _detect_dark() -> bool:
    # 1. freedesktop portal (GNOME >= 42, KDE Plasma 5.x/6): 1 = prefer dark, 2 = prefer light
    answer = _run(["gdbus", "call", "--session", "--dest", "org.freedesktop.portal.Desktop",
                   "--object-path", "/org/freedesktop/portal/desktop",
                   "--method", "org.freedesktop.portal.Settings.Read",
                   "org.freedesktop.appearance", "color-scheme"])
    match = re.search(r"uint32\s+(\d)", answer)
    if match and match.group(1) in "12":
        return match.group(1) == "1"
    # 2. GNOME settings
    answer = _run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"])
    if "dark" in answer:
        return True
    if "default" in answer or "light" in answer:
        return False
    answer = _run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"])
    if "dark" in answer.lower():
        return True
    # 3. KDE
    for tool in ("kreadconfig6", "kreadconfig5"):
        scheme = _run([tool, "--group", "General", "--key", "ColorScheme"])
        if scheme.strip():
            return "dark" in scheme.lower()
    # 4. GTK_THEME environment variable
    return "dark" in (os.environ.get("GTK_THEME") or "").lower()


def prefers_dark() -> bool:
    global _dark_cache
    if _dark_cache is None:
        try:
            _dark_cache = _detect_dark()
        except Exception:
            _dark_cache = False
    return _dark_cache


def style_window(window, dark: bool) -> None:
    """Nothing to do: the window manager draws the decorations."""


def work_area(window=None) -> tuple:
    """(left, top, right, bottom) of the area free of panels, from _NET_WORKAREA when available."""
    output = _run(["xprop", "-root", "_NET_WORKAREA"])
    numbers = [int(n) for n in re.findall(r"-?\d+", output.split("=", 1)[-1])] if "=" in output else []
    if len(numbers) >= 4 and numbers[2] > 0 and numbers[3] > 0:
        left, top, width, height = numbers[:4]
        return left, top, left + width, top + height
    if window is not None:
        return 0, 0, window.winfo_screenwidth(), window.winfo_screenheight()
    return 0, 0, 1280, 720
