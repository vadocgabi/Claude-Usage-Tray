"""Shared UI building blocks: design tokens, desktop theme detection and flat widgets (tkinter)."""
from __future__ import annotations

import base64
import io
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Optional

from . import system

# First installed family wins: Windows, then the common Linux desktop fonts.
FONT_FAMILIES = ("Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", "Cantarell", "Ubuntu",
                 "DejaVu Sans", "Liberation Sans", "Helvetica", "Arial")


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
    """Follows the desktop's dark/light preference."""
    return DARK if system.prefers_dark() else LIGHT


def usage_color(theme: Theme, pct: float) -> str:
    if pct >= 90:
        return theme.crit
    if pct >= 70:
        return theme.warn
    return theme.ok


_family: Optional[str] = None


def font(root: tk.Misc, size: int = 10, bold: bool = False) -> tuple:
    global _family
    if _family is None:
        installed = set(root.tk.call("font", "families"))
        _family = next((name for name in FONT_FAMILIES if name in installed), "TkDefaultFont")
    return (_family, size, "bold" if bold else "normal")


def style_window(window: tk.Misc, theme: Theme) -> None:
    """Native window styling where the platform supports it (dark title bar and rounded corners)."""
    system.style_window(window, theme.name == "dark")


def work_area(window: Optional[tk.Misc] = None) -> tuple:
    """(left, top, right, bottom) of the screen area not covered by panels or the taskbar."""
    return system.work_area(window)


def set_window_icon(window: tk.Misc) -> None:
    """The tray icon artwork as the window icon (taskbar / title bar)."""
    try:
        from .icon import make_icon
        buffer = io.BytesIO()
        make_icon(None, "both").save(buffer, "PNG")
        image = tk.PhotoImage(data=base64.b64encode(buffer.getvalue()))
        window.iconphoto(True, image)
        window._icon_image = image   # keep a reference, Tk does not
    except Exception:
        pass


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
