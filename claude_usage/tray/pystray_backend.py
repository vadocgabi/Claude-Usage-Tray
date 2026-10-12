"""pystray backend: the Windows tray, and the XEmbed tray on Linux desktops without StatusNotifier."""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional

from . import BaseTray, Item

log = logging.getLogger("claude_usage")


def _label(item: Item):
    return lambda _menu_item: item.label()


def _action(item: Item):
    def run(icon, menu_item) -> None:   # pystray inspects the signature: exactly two parameters
        item.action()
    return run


def _checked(item: Item):
    return lambda _menu_item: item.is_checked()


def _visible(item: Item):
    return lambda _menu_item: item.is_visible()


def build_menu(pystray, items: list):
    entries = []
    for item in items:
        if item.separator:
            entries.append(pystray.Menu.SEPARATOR)
            continue
        if item.children is not None:
            entries.append(pystray.MenuItem(_label(item), build_menu(pystray, item.children)))
            continue
        entries.append(pystray.MenuItem(
            _label(item), _action(item) if item.action else None,
            checked=_checked(item) if item.checked else None, radio=item.radio,
            enabled=item.enabled and item.action is not None, visible=_visible(item) if item.visible else None,
            default=item.default))
    return pystray.Menu(*entries)


class PystrayTray(BaseTray):
    def __init__(self, name: str, image, title: str, items: list):
        super().__init__(name, image, title, items)
        if sys.platform.startswith("linux"):
            # StatusNotifier is handled by our own backend; here only the X11 system tray is left. pystray's
            # auto-detection would try GTK/AppIndicator first and can crash when only part of GTK is installed.
            os.environ.setdefault("PYSTRAY_BACKEND", "xorg")
        import pystray
        self._icon = pystray.Icon(name, image, title, menu=build_menu(pystray, items))
        self._notifier = None
        if sys.platform.startswith("linux"):
            from .notifier import Notifier
            self._notifier = Notifier()      # the XEmbed backend cannot show notifications itself

    def set_icon(self, image) -> None:
        self._icon.icon = image

    def set_title(self, title: str) -> None:
        self._icon.title = title[:127]

    def refresh_menu(self) -> None:
        self._icon.update_menu()

    def notify(self, message: str, title: str) -> None:
        if self._notifier is not None:
            self._notifier.send(title, message)
        else:
            self._icon.notify(message, title)

    def run(self) -> None:
        self._icon.run()

    def stop(self) -> None:
        self._icon.stop()
