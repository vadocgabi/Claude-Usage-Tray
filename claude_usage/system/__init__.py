"""Operating-system integration behind one small interface.

Every OS-specific call of the application goes through this module; the implementation is chosen
once at import time (`windows.py`, `linux.py`, or `fallback.py` for anything else).

Interface (all functions are safe to call from any thread):
    data_dir()                      per-user folder for config, settings and the log
    protect(name, value) -> str     value to store in config.json (encrypted or a keyring reference)
    unprotect(stored) -> str        the secret back from what `protect` returned
    native_credentials() -> str     Claude Code credentials JSON from the OS store, or ""
    autostart_enabled() -> bool
    set_autostart(enable, command)
    acquire_single_instance() -> bool   False when another instance already runs
    system_language() -> str            'hu' or 'en'
    prefers_dark() -> bool
    style_window(window, dark)          native window styling (dark title bar, ...)
    work_area(window) -> (l, t, r, b)   screen area not covered by panels
    FLYOUT_BORDERLESS                   True where a borderless focus-closing popup works well
"""
from __future__ import annotations

import sys

if sys.platform == "win32":
    from . import windows as _impl
elif sys.platform.startswith("linux"):
    from . import linux as _impl
else:
    from . import fallback as _impl

data_dir = _impl.data_dir
protect = _impl.protect
unprotect = _impl.unprotect
native_credentials = _impl.native_credentials
autostart_enabled = _impl.autostart_enabled
set_autostart = _impl.set_autostart
acquire_single_instance = _impl.acquire_single_instance
system_language = _impl.system_language
prefers_dark = _impl.prefers_dark
style_window = _impl.style_window
work_area = _impl.work_area
FLYOUT_BORDERLESS = _impl.FLYOUT_BORDERLESS
NAME = _impl.NAME
