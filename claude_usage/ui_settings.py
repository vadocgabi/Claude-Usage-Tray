"""Settings window: choose the authentication method and enter the claude.ai credentials."""
from __future__ import annotations

import re
import threading
import tkinter as tk
import webbrowser
from typing import Callable

from . import REPO_URL, USAGE_PAGE
from .config import AUTH_MODES, has_cookie_login, save_credentials
from .i18n import credit_text, tr
from .sources import UsageError, fetch_usage, read_oauth_credentials
from .ui_common import button, card, current_theme, entry, font, label, style_window

UUID_RE = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")
WIDTH = 520


def clean_session_key(raw: str) -> str:
    """Accepts the bare value, a quoted value or a pasted `sessionKey=...` cookie pair."""
    value = raw.strip().strip('"')
    return value.split("=", 1)[1] if value.lower().startswith("sessionkey=") else value


def extract_org_id(raw: str) -> str:
    """Accepts the bare id or any pasted URL containing it."""
    match = UUID_RE.search(raw)
    return match.group(0) if match else raw.strip()


def show_settings(cfg: dict, lang: str, on_saved: Callable[[dict], None]) -> None:
    """Runs a modal-style settings window; call from its own thread."""
    theme = current_theme()
    T = lambda key, **kw: tr(lang, key, **kw)

    root = tk.Tk()
    root.title(T("set_title"))
    root.configure(bg=theme.bg)
    root.resizable(False, False)
    root.attributes("-topmost", True)
    body = tk.Frame(root, bg=theme.bg, padx=18, pady=16)
    body.pack(fill="both")

    label(body, theme, T("set_title_short"), 16, True, bg=theme.bg).pack(anchor="w")
    label(body, theme, T("set_intro"), 9, muted=True, bg=theme.bg, wraplength=WIDTH - 40,
          justify="left").pack(anchor="w", pady=(2, 12))

    # ---- authentication method
    method = card(body, theme, pady=(0, 10))
    label(method, theme, T("set_method"), 10, True).pack(anchor="w", pady=(0, 6))
    mode = tk.StringVar(value=cfg["auth_mode"])
    for value in AUTH_MODES:
        tk.Radiobutton(method, text=T(f"mode_{value}"), variable=mode, value=value, command=lambda: sync(),
                       font=font(root, 10), bg=theme.card, fg=theme.text, activebackground=theme.card,
                       activeforeground=theme.text, selectcolor=theme.bg, bd=0, highlightthickness=0,
                       anchor="w").pack(fill="x")
    oauth_status = label(method, theme, "", 9, muted=True, wraplength=WIDTH - 70, justify="left")
    oauth_status.pack(anchor="w", pady=(8, 0))

    # ---- claude.ai credentials
    login = card(body, theme, pady=(0, 10))
    label(login, theme, T("set_cookie_title"), 10, True).pack(anchor="w", pady=(0, 6))
    org, key, clearance = (tk.StringVar(value=cfg["org_id"]), tk.StringVar(value=cfg["session_key"]),
                           tk.StringVar(value=cfg["cf_clearance"]))
    fields = []
    for title, variable, secret in (("set_org", org, False), ("set_key", key, True), ("set_cf", clearance, True)):
        label(login, theme, T(title), 9, muted=True).pack(anchor="w", pady=(6, 2))
        field = entry(login, theme, variable, secret)
        field.pack(fill="x", ipady=5)
        fields.append((field, secret))
    reveal = tk.BooleanVar(value=False)
    tk.Checkbutton(login, text=T("set_show"), variable=reveal, font=font(root, 9), bg=theme.card, fg=theme.muted,
                   activebackground=theme.card, activeforeground=theme.text, selectcolor=theme.card,
                   bd=0, highlightthickness=0,
                   command=lambda: [f.configure(show="" if reveal.get() or not s else "•") for f, s in fields]
                   ).pack(anchor="w", pady=(6, 0))
    help_link = label(login, theme, T("set_help"), 9, cursor="hand2")
    help_link.configure(fg=theme.accent)
    help_link.pack(anchor="w", pady=(6, 0))
    help_link.bind("<Button-1>", lambda event: webbrowser.open(USAGE_PAGE))
    label(login, theme, T("set_hint"), 8, muted=True, wraplength=WIDTH - 70, justify="left").pack(anchor="w")

    # ---- status + actions
    status = tk.StringVar()
    status_label = tk.Label(body, textvariable=status, font=font(root, 9), bg=theme.bg, fg=theme.muted,
                            wraplength=WIDTH - 40, justify="left")
    status_label.pack(anchor="w", pady=(0, 8))

    def sync() -> None:
        creds = read_oauth_credentials()
        if creds:
            plan = f" ({creds.plan})" if creds.plan else ""
            oauth_status.configure(text=T("set_oauth_found", plan=plan), fg=theme.ok)
        else:
            oauth_status.configure(text=T("set_oauth_missing"), fg=theme.warn)
        for field, _ in fields:
            field.configure(state="disabled" if mode.get() == "oauth" else "normal")

    def say(text: str, colour: str) -> None:
        status.set(text)
        status_label.configure(fg=colour)

    def collect() -> dict:
        return dict(cfg, auth_mode=mode.get(), org_id=extract_org_id(org.get()),
                    session_key=clean_session_key(key.get()), cf_clearance=clearance.get().strip())

    def usable(candidate: dict) -> bool:
        wanted_cookie = candidate["auth_mode"] in ("auto", "cookie")
        wanted_oauth = candidate["auth_mode"] in ("auto", "oauth")
        return (wanted_oauth and read_oauth_credentials() is not None) or \
               (wanted_cookie and has_cookie_login(candidate))

    def test() -> None:
        candidate = collect()
        if not usable(candidate):
            say(T("set_missing"), theme.warn)
            return
        say(T("set_testing"), theme.muted)

        def work() -> None:
            try:
                usage = fetch_usage(candidate)
                session = f"{usage.session.pct:.0f}" if usage.session else "-"
                week = f"{usage.weekly.pct:.0f}" if usage.weekly else "-"
                result = (T("set_test_ok", s=session, w=week, src=T("src_" + usage.source)), theme.ok)
            except UsageError as e:
                result = (T("set_test_fail", e=T(e.key, e=e.arg)), theme.crit)
            except Exception as e:
                result = (T("set_test_fail", e=str(e)[:120]), theme.crit)
            try:
                root.after(0, lambda: say(*result))
            except tk.TclError:
                pass

        threading.Thread(target=work, daemon=True).start()

    def save() -> None:
        candidate = collect()
        if not usable(candidate):
            say(T("set_missing"), theme.warn)
            return
        save_credentials(candidate)
        root.destroy()
        on_saved(candidate)

    actions = tk.Frame(body, bg=theme.bg)
    actions.pack(fill="x")
    credit = label(actions, theme, credit_text(lang), 8, muted=True, bg=theme.bg, cursor="hand2")
    credit.pack(side="left")
    credit.bind("<Button-1>", lambda event: webbrowser.open(REPO_URL))
    button(actions, theme, T("set_save"), save, primary=True).pack(side="right")
    button(actions, theme, T("set_cancel"), root.destroy, bg=theme.bg).pack(side="right", padx=8)
    button(actions, theme, T("set_test"), test, bg=theme.bg).pack(side="right")

    sync()
    style_window(root, theme)
    root.update_idletasks()
    x = (root.winfo_screenwidth() - root.winfo_reqwidth()) // 2
    y = (root.winfo_screenheight() - root.winfo_reqheight()) // 3
    root.geometry(f"+{x}+{y}")
    root.mainloop()
