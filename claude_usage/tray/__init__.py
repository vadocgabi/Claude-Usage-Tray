"""Tray abstraction: one neutral menu model, several backends.

    Windows        pystray (Win32)
    Linux          our own StatusNotifierItem over D-Bus (GNOME with the AppIndicator extension, KDE,
                   XFCE, Cinnamon, MATE, LXQt, Budgie, waybar ...), else pystray's XEmbed backend,
                   else no tray at all: the application then shows its details window instead.
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from typing import Callable, Optional, Union

log = logging.getLogger("claude_usage")

Text = Union[str, Callable[[], str]]


@dataclass
class Item:
    """One menu entry (or separator / submenu). Callables are evaluated each time the menu is shown."""
    text: Text = ""
    action: Optional[Callable[[], None]] = None
    checked: Optional[Callable[[], bool]] = None
    radio: bool = False
    enabled: bool = True
    visible: Optional[Callable[[], bool]] = None
    default: bool = False                       # activated by a left click on the icon
    children: Optional[list] = None
    separator: bool = False

    def label(self) -> str:
        return self.text() if callable(self.text) else self.text

    def is_visible(self) -> bool:
        return True if self.visible is None else bool(self.visible())

    def is_checked(self) -> bool:
        return bool(self.checked()) if self.checked is not None else False


SEPARATOR = Item(separator=True)


def find_default(items: list) -> Optional[Item]:
    for item in items:
        if item.default and item.action:
            return item
    return None


class BaseTray:
    """Interface every backend implements. `run()` blocks until `stop()`."""

    def __init__(self, name: str, image, title: str, items: list):
        self.name, self.image, self.title, self.items = name, image, title, items
        self.on_unavailable: Optional[Callable[[], None]] = None

    def set_icon(self, image) -> None:
        raise NotImplementedError

    def set_title(self, title: str) -> None:
        raise NotImplementedError

    def refresh_menu(self) -> None:
        raise NotImplementedError

    def notify(self, message: str, title: str) -> None:
        raise NotImplementedError

    def run(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


def create_tray(name: str, image, title: str, items: list) -> BaseTray:
    """Best available tray backend for this platform / session."""
    forced = os.environ.get("CLAUDE_USAGE_TRAY", "").lower()   # sni | xorg | window (testing aid)
    if sys.platform.startswith("linux"):
        from . import linux_select
        return linux_select.choose(name, image, title, items, forced)
    from .pystray_backend import PystrayTray
    return PystrayTray(name, image, title, items)
