"""Flyout with the full usage details, opened by left-clicking the tray icon."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime, timezone
from typing import Callable

from . import fmt
from .i18n import STRINGS, tr, units
from .insights import pace_pct, seconds_to_limit
from .model import Limit
from .ui_common import (Bar, button, card, current_theme, font, label, style_window, usage_color,
                        work_area)

WIDTH = 400
POLL_MS = 1000


class DetailsWindow:
    """Borderless card that closes on focus loss, like a Windows 11 flyout."""

    def __init__(self, app, on_settings: Callable, on_refresh: Callable):
        self.app, self.on_settings, self.on_refresh = app, on_settings, on_refresh
        self.theme = current_theme()
        self.shown_version = -1

    def run(self) -> None:
        theme = self.theme
        self.root = root = tk.Tk()
        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=theme.border)
        self.body = tk.Frame(root, bg=theme.bg, padx=14, pady=14)
        self.body.pack(padx=1, pady=1, fill="both")
        root.bind("<Escape>", lambda event: root.destroy())
        root.bind("<FocusOut>", lambda event: root.after(150, self._close_if_unfocused))
        self._refresh_view()
        root.deiconify()
        style_window(root, theme)
        root.focus_force()
        root.mainloop()

    # ------------------------------------------------------------ lifecycle
    def _close_if_unfocused(self) -> None:
        try:
            if self.root.focus_displayof() is None:
                self.root.destroy()
        except tk.TclError:
            pass

    def _refresh_view(self) -> None:
        try:
            if self.app.version != self.shown_version:
                self._render()
            self.root.after(POLL_MS, self._refresh_view)
        except tk.TclError:
            pass

    def _place(self) -> None:
        self.root.update_idletasks()
        _, _, right, bottom = work_area()
        height = self.root.winfo_reqheight()
        self.root.geometry(f"{WIDTH}x{height}+{right - WIDTH - 12}+{bottom - height - 12}")

    # ------------------------------------------------------------ rendering
    def _render(self) -> None:
        self.shown_version = self.app.version
        lang, theme = self.app.lang, self.theme
        snapshot = self.app.snapshot
        for child in self.body.winfo_children():
            child.destroy()

        header = tk.Frame(self.body, bg=theme.bg)
        header.pack(fill="x", pady=(0, 10))
        label(header, theme, tr(lang, "title"), 14, True, bg=theme.bg).pack(side="left")
        close = label(header, theme, "✕", 11, muted=True, bg=theme.bg, cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda event: self.root.destroy())
        if snapshot.usage and snapshot.usage.plan:
            pill = label(header, theme, snapshot.usage.plan, 9, True, bg=theme.card, padx=8, pady=1)
            pill.configure(highlightthickness=1, highlightbackground=theme.border)
            pill.pack(side="right", padx=(0, 10))

        if snapshot.error and not snapshot.usage:
            self._message(tr(lang, snapshot.error[0], e=snapshot.error[1]))
        elif snapshot.usage:
            now = datetime.now(timezone.utc)
            main = [lim for lim in (snapshot.usage.session, snapshot.usage.weekly) if lim]
            for limit in main:
                self._limit_card(limit, now)
            extras = [*snapshot.usage.models, *([snapshot.usage.extra] if snapshot.usage.extra else [])]
            if extras:
                self._compact_card(extras)
            if snapshot.usage.breakdown:
                self._breakdown(snapshot.usage.breakdown)
        if snapshot.stats:
            self._tokens(snapshot.stats)
        self._footer(snapshot)
        self._place()

    def _message(self, text: str) -> None:
        box = card(self.body, self.theme, pady=(0, 8))
        label(box, self.theme, text, 10, wraplength=WIDTH - 60, justify="left").pack(anchor="w")

    def _limit_title(self, limit: Limit) -> str:
        lang = self.app.lang
        if limit.key == "session":
            return tr(lang, "d_session")
        if limit.key == "weekly":
            return tr(lang, "d_week")
        if limit.key == "extra":
            return tr(lang, "d_extra")
        return tr(lang, "d_model", m=limit.label)

    def _limit_card(self, limit: Limit, now: datetime) -> None:
        lang, theme = self.app.lang, self.theme
        box = card(self.body, theme, pady=(0, 8))
        top = tk.Frame(box, bg=theme.card)
        top.pack(fill="x")
        label(top, theme, self._limit_title(limit), 10, True).pack(side="left")
        tk.Label(top, text=f"{limit.pct:.0f}%", font=font(top, 13, True), bg=theme.card,
                 fg=usage_color(theme, limit.pct)).pack(side="right")
        bar = Bar(box, theme)
        bar.pack(fill="x", pady=(8, 6))
        pace = pace_pct(limit, now)
        bar.set(limit.pct, pace)

        details = []
        resets = fmt.parse_iso(limit.resets_at)
        if resets is not None:
            left = (resets - now).total_seconds()
            details.append(tr(lang, "d_resets", t=fmt.duration(left, units(lang)),
                              at=fmt.local_time(limit.resets_at, limit.window_hours == 168, STRINGS[lang]["days"])))
        if pace is not None:
            details.append(tr(lang, "d_pace", p=f"{pace:.0f}"))
        label(box, theme, "  ·  ".join(details), 9, muted=True).pack(anchor="w")

        eta = seconds_to_limit(limit, now)
        if eta is not None and limit.key in ("session", "weekly") and limit.pct < 100:
            warning = label(box, theme, tr(lang, "d_eta", t=fmt.duration(eta, units(lang))), 9, True)
            warning.configure(fg=theme.warn)
            warning.pack(anchor="w", pady=(2, 0))

    def _compact_card(self, limits: list) -> None:
        """Per-model weekly limits and extra usage as one row each: name, thin bar, percentage."""
        theme = self.theme
        box = card(self.body, theme, pady=(0, 8))
        for limit in limits:
            row = tk.Frame(box, bg=theme.card)
            row.pack(fill="x", pady=3)
            label(row, theme, self._limit_title(limit), 9, muted=True, width=16, anchor="w").pack(side="left")
            tk.Label(row, text=f"{limit.pct:.0f}%", font=font(row, 10, True), bg=theme.card, width=5,
                     anchor="e", fg=usage_color(theme, limit.pct)).pack(side="right")
            bar = Bar(row, theme, height=6)
            bar.pack(side="left", fill="x", expand=True, padx=8)
            bar.set(limit.pct, pace_pct(limit))

    def _breakdown(self, rows: list) -> None:
        theme, lang = self.theme, self.app.lang
        text = "  ·  ".join(f"{name} {pct:.0f}%" for name, pct in rows)
        label(self.body, theme, tr(lang, "d_breakdown") + ": " + text, 9, muted=True, bg=theme.bg,
              wraplength=WIDTH - 40, justify="left").pack(anchor="w", pady=(0, 8))

    def _tokens(self, stats) -> None:
        theme, lang = self.theme, self.app.lang
        box = card(self.body, theme, pady=(0, 8))
        label(box, theme, tr(lang, "d_tokens"), 10, True).pack(anchor="w")
        label(box, theme, tr(lang, "d_tokens_line", today=fmt.tokens(stats.today), week=fmt.tokens(stats.week)),
              10).pack(anchor="w", pady=(4, 0))
        top = ", ".join(f"{name} {fmt.tokens(count)}" for name, count in stats.top_models[:3])
        label(box, theme, top, 9, muted=True, wraplength=WIDTH - 60, justify="left").pack(anchor="w")

    def _footer(self, snapshot) -> None:
        theme, lang = self.theme, self.app.lang
        info = []
        if snapshot.usage:
            info.append(tr(lang, "src_" + snapshot.usage.source))
        if snapshot.updated:
            info.append(tr(lang, "updated", t=f"{snapshot.updated:%H:%M:%S}"))
        if snapshot.error and snapshot.usage:
            info.append(tr(lang, "d_stale"))
        label(self.body, theme, "  ·  ".join(info), 8, muted=True, bg=theme.bg).pack(anchor="w", pady=(2, 8))
        if snapshot.error and snapshot.usage:
            warn = label(self.body, theme, tr(lang, snapshot.error[0], e=snapshot.error[1]), 8, bg=theme.bg,
                         wraplength=WIDTH - 40, justify="left")
            warn.configure(fg=theme.warn)
            warn.pack(anchor="w", pady=(0, 8))
        row = tk.Frame(self.body, bg=theme.bg)
        row.pack(fill="x")
        button(row, theme, tr(lang, "refresh"), self.on_refresh, bg=theme.bg).pack(side="left")
        button(row, theme, tr(lang, "settings"), self._settings, bg=theme.bg).pack(side="left", padx=8)

    def _settings(self) -> None:
        self.root.destroy()
        self.on_settings()
