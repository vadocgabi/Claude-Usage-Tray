"""Chooses the tray backend on Linux."""
from __future__ import annotations

import logging
import os

from . import BaseTray

log = logging.getLogger("claude_usage")


def xembed_tray_present() -> bool:
    """True when an X11 system-tray manager owns the _NET_SYSTEM_TRAY selection (XFCE, MATE, i3bar ...)."""
    if not os.environ.get("DISPLAY"):
        return False
    try:
        from Xlib import display
        connection = display.Display()
        try:
            atom = connection.intern_atom(f"_NET_SYSTEM_TRAY_S{connection.get_default_screen()}")
            return connection.get_selection_owner(atom) != 0
        finally:
            connection.close()
    except Exception:
        return False


class WindowOnlyTray(BaseTray):
    """No tray anywhere: run without an icon; the application shows its window instead."""

    def __init__(self, name, image, title, items):
        super().__init__(name, image, title, items)
        import threading
        self._stop = threading.Event()

    def set_icon(self, image) -> None:
        pass

    def set_title(self, title: str) -> None:
        pass

    def refresh_menu(self) -> None:
        pass

    def notify(self, message: str, title: str) -> None:
        from .notifier import Notifier
        Notifier().send(title, message)

    def run(self) -> None:
        if self.on_unavailable:
            self.on_unavailable()
        self._stop.wait()

    def stop(self) -> None:
        self._stop.set()


def choose(name, image, title, items, forced: str = "") -> BaseTray:
    from . import sni
    from .pystray_backend import PystrayTray

    if forced == "window":
        return WindowOnlyTray(name, image, title, items)
    if forced == "xorg":
        return PystrayTray(name, image, title, items)

    bus = sni.session_bus_available()
    if forced == "sni" and bus:
        return sni.SniTray(name, image, title, items)
    if bus and sni.watcher_present():
        log.info("tray: StatusNotifierItem")
        return sni.SniTray(name, image, title, items)
    if xembed_tray_present():
        log.info("tray: XEmbed (pystray xorg)")
        return PystrayTray(name, image, title, items)
    if bus:
        # a watcher may appear later (GNOME extension loading at login); the tray registers then, and
        # `on_unavailable` fires if that does not happen within a few seconds
        log.info("tray: StatusNotifierItem (waiting for a watcher)")
        return sni.SniTray(name, image, title, items)
    log.info("tray: none, window only")
    return WindowOnlyTray(name, image, title, items)
