"""`--diagnose`: a plain-text report of what works on this system (for support and CI)."""
from __future__ import annotations

import os
import platform
import sys
from typing import Callable

from . import __version__


def _check(name: str, test: Callable[[], str]) -> tuple:
    try:
        return name, True, test()
    except Exception as e:   # a diagnostic must never crash
        return name, False, f"{type(e).__name__}: {e}"


def run(out: str = "") -> int:
    """Prints the report (or writes it to `out`, for the console-less Windows exe); 1 if something essential fails."""
    from . import system

    def tk_check() -> str:
        import tkinter
        if not (os.environ.get("DISPLAY") or sys.platform == "win32"):
            return f"Tk {tkinter.TkVersion} available (no display to open a window)"
        root = tkinter.Tk()
        root.withdraw()
        families = len(set(root.tk.call("font", "families")))
        root.destroy()
        return f"Tk {tkinter.TkVersion}, window opened, {families} font families"

    def tray_check() -> str:
        if sys.platform.startswith("linux"):
            from .tray import sni
            if not sni.session_bus_available():
                return "no D-Bus session bus"
            return "StatusNotifierWatcher present" if sni.watcher_present() else "no StatusNotifierWatcher"
        return "native"

    def xembed_check() -> str:
        from .tray.linux_select import xembed_tray_present
        return "X11 tray manager present" if xembed_tray_present() else "no X11 tray manager (or no DISPLAY)"

    def keyring_check() -> str:
        from .system import linux
        backend = linux._keyring()
        return type(backend.get_keyring()).__name__ if backend else "none; secrets are kept in the 0600 config file"

    def icon_check() -> str:
        from .icon import make_icon
        image = make_icon(None, "both")
        return f"{image.size[0]}x{image.size[1]} RGBA"

    def curl_check() -> str:
        import curl_cffi
        return f"curl_cffi {curl_cffi.__version__}"

    def paths_check() -> str:
        from .paths import BASE
        probe = BASE / ".write-test"
        probe.write_text("x")
        probe.unlink()
        return str(BASE)

    def claude_login() -> str:
        from .sources import read_oauth_credentials
        creds = read_oauth_credentials()
        if not creds:
            return "not found (cookie mode only)"
        return f"found ({creds.plan or 'plan unknown'}), expired={creds.is_expired()}"

    rows = [
        ("application", True, f"Claude Usage Tray {__version__}"),
        ("python", True, f"{platform.python_version()} on {platform.platform()}"),
        ("platform layer", True, system.NAME),
        _check("config folder writable", paths_check),
        _check("Pillow icon rendering", icon_check),
        _check("Tk interface", tk_check),
        _check("tray (D-Bus)", tray_check),
    ]
    if sys.platform.startswith("linux"):
        rows += [_check("tray (X11 XEmbed)", xembed_check), _check("secret storage", keyring_check)]
    rows += [_check("cookie mode (curl_cffi)", curl_check), _check("Claude Code login", claude_login)]

    width = max(len(name) for name, _, _ in rows)
    lines = [f"{'OK  ' if ok else 'FAIL'}  {name.ljust(width)}  {detail}" for name, ok, detail in rows]
    report = "\n".join(lines)
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            handle.write(report + "\n")
    elif sys.stdout is not None:
        print(report)
    essential = {"config folder writable", "Pillow icon rendering", "Tk interface"}
    return 1 if any(not ok and name in essential for name, ok, _ in rows) else 0
