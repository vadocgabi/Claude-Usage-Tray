"""Shared UI building blocks: design tokens, Windows theme detection and flat widgets (tkinter)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Optional

FONT = "Segoe UI Variable Text"
FONT_FALLBACK = "Segoe UI"


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    card: str
    border: str
    text: str
    muted: str
    track: str
    accent: str
    accent_text: str
    ok: str
    warn: str
    crit: str
    hover: str


DARK = Theme("dark", bg="#1b1b1f", card="#25252b", border="#33333b", text="#f3f3f6", muted="#9b9ba6",
             track="#34343d", accent="#4f8cff", accent_text="#ffffff", ok="#4f8cff", warn="#f5a623",
             crit="#ef5350", hover="#2f2f37")
LIGHT = Theme("light", bg="#f4f4f7", card="#ffffff", border="#e2e2e9", text="#16161b", muted="#6a6a77",
              track="#e7e7ee", accent="#2563eb", accent_text="#ffffff", ok="#2563eb", warn="#e08600",
              crit="#d93636", hover="#ececf2")


def current_theme() -> Theme:
    """Follows the Windows 'app mode' setting."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return LIGHT if winreg.QueryValueEx(key, "AppsUseLightTheme")[0] else DARK
    except OSError:
        return LIGHT


def usage_color(theme: Theme, pct: float) -> str:
    if pct >= 90:
        return theme.crit
    if pct >= 70:
        return theme.warn
    return theme.ok


def font(root: tk.Misc, size: int = 10, bold: bool = False) -> tuple:
    families = set(root.tk.call("font", "families"))
    family = FONT if FONT in families else FONT_FALLBACK
    return (family, size, "bold" if bold else "normal")


def style_window(window: tk.Misc, theme: Theme) -> None:
    """Dark title bar and rounded corners on Windows 10/11 (silently ignored where unsupported)."""
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        dwm = ctypes.windll.dwmapi
        for attribute, value in ((20, int(theme.name == "dark")), (33, 2)):  # dark mode, round corners
            dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(ctypes.c_int(value)), 4)
    except (OSError, AttributeError):
        pass


def work_area() -> tuple:
    """(left, top, right, bottom) of the screen area not covered by the taskbar."""
    rect = ctypes.wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
    return rect.left, rect.top, rect.right, rect.bottom


class Bar(tk.Canvas):
    """Rounded progress bar with an optional 'on pace' marker."""

    def __init__(self, parent: tk.Misc, theme: Theme, height: int = 8):
        super().__init__(parent, height=height, bg=theme.card, highlightthickness=0, bd=0)
        self.theme, self.bar_height = theme, height
        self.pct: float = 0
        self.pace: Optional[float] = None
        self.bind("<Configure>", lambda event: self._draw())

    def set(self, pct: float, pace: Optional[float] = None) -> None:
        self.pct, self.pace = pct, pace
        self._draw()

    def _pill(self, end: float, color: str) -> None:
        radius = self.bar_height / 2
        self.create_line(radius, radius, max(radius, end - radius), radius, width=self.bar_height,
                         capstyle="round", fill=color)

    def _draw(self) -> None:
        self.delete("all")
        width = self.winfo_width()
        if width <= 1:
            return
        self._pill(width, self.theme.track)
        fill = width * max(0.0, min(self.pct, 100)) / 100
        if fill > 0:
            self._pill(max(fill, self.bar_height), usage_color(self.theme, self.pct))
        if self.pace is not None and 0 < self.pace < 100:
            x = width * self.pace / 100
            self.create_line(x, 0, x, self.bar_height, fill=self.theme.text, width=2)


def label(parent: tk.Misc, theme: Theme, text: str = "", size: int = 10, bold: bool = False,
          muted: bool = False, bg: Optional[str] = None, **options) -> tk.Label:
    return tk.Label(parent, text=text, font=font(parent, size, bold), bg=bg or theme.card,
                    fg=theme.muted if muted else theme.text, **options)


def button(parent: tk.Misc, theme: Theme, text: str, command: Callable, primary: bool = False,
           bg: Optional[str] = None) -> tk.Label:
    """Flat button (a Label, so colours are fully themeable)."""
    normal = theme.accent if primary else (bg or theme.card)
    hover = theme.accent if primary else theme.hover
    widget = tk.Label(parent, text=text, font=font(parent, 10, primary), bg=normal,
                      fg=theme.accent_text if primary else theme.text, padx=14, pady=6, cursor="hand2",
                      highlightthickness=0 if primary else 1, highlightbackground=theme.border)
    widget.bind("<Button-1>", lambda event: command())
    widget.bind("<Enter>", lambda event: widget.configure(bg=hover))
    widget.bind("<Leave>", lambda event: widget.configure(bg=normal))
    return widget


def entry(parent: tk.Misc, theme: Theme, variable: tk.StringVar, secret: bool = False) -> tk.Entry:
    return tk.Entry(parent, textvariable=variable, font=font(parent, 10), bg=theme.bg, fg=theme.text,
                    insertbackground=theme.text, relief="flat", highlightthickness=1,
                    highlightbackground=theme.border, highlightcolor=theme.accent,
                    show="•" if secret else "")


def card(parent: tk.Misc, theme: Theme, **pack) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.card, highlightthickness=1, highlightbackground=theme.border,
                     padx=14, pady=12)
    frame.pack(fill="x", **pack)
    return frame
