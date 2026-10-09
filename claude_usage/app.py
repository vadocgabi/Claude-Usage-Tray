"""The tray application: icon, menu, polling thread and notifications."""
from __future__ import annotations

import logging
import random
import threading
import webbrowser
from datetime import datetime, timezone
from typing import Callable

import pystray

from . import USAGE_PAGE, __version__, autostart, updates
from .config import ICON_MODES, INTERVALS, load_config, save_preferences
from .i18n import LANGS, credit_text, resolve_language, tr, units
from .icon import make_icon
from .insights import Alert, AlertTracker, poll_delay
from .localstats import LocalStats
from .fmt import duration, local_time, parse_iso
from .model import Limit, Snapshot
from .sources import UsageError, fetch_usage, is_configured
from .ui_details import DetailsWindow
from .ui_settings import show_settings

log = logging.getLogger("claude_usage")
JITTER_SECONDS = 30


class App:
    def __init__(self):
        self.cfg = load_config()
        self.lang = resolve_language(self.cfg["language"])
        self.snapshot = Snapshot()
        self.version = 0                    # bumped on every change, lets open windows redraw
        self.alerts = AlertTracker(tuple(self.cfg["notify_thresholds"]))
        self.local_stats = LocalStats()
        self.backoff = 0.0
        self.wake, self.stop = threading.Event(), threading.Event()
        self._open_windows: set = set()
        self.icon = pystray.Icon("claude_usage", make_icon(None, self.cfg["icon_mode"]), self.t("title"),
                                 menu=self._build_menu())

    # ------------------------------------------------------------ helpers
    def t(self, key: str, **kwargs) -> str:
        return tr(self.lang, key, **kwargs)

    def _error_text(self) -> str:
        key, arg = self.snapshot.error
        return self.t(key, e=arg)

    def _limit_name(self, limit: Limit) -> str:
        return {"session": self.t("d_session"), "weekly": self.t("d_week")}.get(
            limit.key, limit.label or limit.key)

    def _time(self, limit: Limit, with_day: bool) -> str:
        return local_time(limit.resets_at, with_day, tr(self.lang, "days") if False else self._days())

    def _days(self) -> list:
        from .i18n import STRINGS
        return STRINGS[self.lang]["days"]

    # ------------------------------------------------------------ menu
    def _build_menu(self) -> pystray.Menu:
        item, text = pystray.MenuItem, lambda key: (lambda _: self.t(key))
        return pystray.Menu(
            item(lambda _: self._line_session(), None, enabled=False),
            item(lambda _: self._line_week(), None, enabled=False),
            item(lambda _: self._line_models(), None, enabled=False, visible=lambda _: self._has_models()),
            item(lambda _: self._line_updated(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            item(text("details"), lambda icon, i: self.open_details(), default=True),
            item(text("refresh"), lambda icon, i: self.wake.set()),
            item(text("open_page"), lambda icon, i: webbrowser.open(USAGE_PAGE)),
            pystray.Menu.SEPARATOR,
            item(text("settings"), lambda icon, i: self.open_settings()),
            item(text("autostart"), self._toggle_autostart, checked=lambda i: autostart.is_enabled()),
            item(text("notifications"), self._toggle_notifications, checked=lambda i: self.cfg["notifications"]),
            item(text("interval"), pystray.Menu(*[self._interval_item(s) for s in INTERVALS])),
            item(text("icon_mode"), pystray.Menu(*[self._icon_item(m) for m in ICON_MODES])),
            item(text("language"), pystray.Menu(*[self._language_item(c) for c in LANGS])),
            pystray.Menu.SEPARATOR,
            item(text("check_updates"), lambda icon, i: threading.Thread(target=self._check_updates,
                                                                          daemon=True).start()),
            item(lambda _: credit_text(self.lang), None, enabled=False),
            item(text("quit"), self._quit),
        )

    def _radio(self, label: Callable, selected: Callable, choose: Callable) -> pystray.MenuItem:
        return pystray.MenuItem(label, lambda icon, i: choose(), checked=lambda i: selected(), radio=True)

    def _interval_item(self, seconds: int) -> pystray.MenuItem:
        return self._radio(lambda _: self.t("minutes", n=seconds // 60),
                           lambda: self.cfg["interval_seconds"] == seconds,
                           lambda: self._set_pref("interval_seconds", seconds))

    def _icon_item(self, mode: str) -> pystray.MenuItem:
        return self._radio(lambda _: self.t(f"icon_{mode}"), lambda: self.cfg["icon_mode"] == mode,
                           lambda: self._set_pref("icon_mode", mode))

    def _language_item(self, code: str) -> pystray.MenuItem:
        def choose() -> None:
            self.lang = code
            self._set_pref("language", code)
        return self._radio(lambda _: LANGS[code], lambda: self.lang == code, choose)

    def _line_session(self) -> str:
        usage = self.snapshot.usage
        if not usage:
            return self._error_text() if self.snapshot.error else self.t("loading")
        if not usage.session:
            return "–"
        return self.t("session", p=f"{usage.session.pct:.0f}", t=self._time(usage.session, False))

    def _line_week(self) -> str:
        usage = self.snapshot.usage
        if not usage or not usage.weekly:
            return "–"
        return self.t("week", p=f"{usage.weekly.pct:.0f}", t=self._time(usage.weekly, True))

    def _has_models(self) -> bool:
        return bool(self.snapshot.usage and self.snapshot.usage.models)

    def _line_models(self) -> str:
        models = self.snapshot.usage.models if self.snapshot.usage else []
        return self.t("models_line", m=", ".join(f"{m.label} {m.pct:.0f}%" for m in models))

    def _line_updated(self) -> str:
        updated = self.snapshot.updated
        line = self.t("updated", t=f"{updated:%H:%M:%S}") if updated else self.t("no_data")
        if self.snapshot.usage and self.snapshot.usage.plan:
            line = f"{self.snapshot.usage.plan}  ·  {line}"
        if self.snapshot.stale:
            line += self.t("error_suffix", e=self._error_text())
        return line

    # ------------------------------------------------------------ actions
    def _set_pref(self, key: str, value) -> None:
        self.cfg[key] = value
        save_preferences(self.cfg)
        self._publish()
        if key == "interval_seconds":
            self.wake.set()

    def _toggle_autostart(self, icon, item) -> None:
        try:
            autostart.set_enabled(not autostart.is_enabled())
        except OSError:
            log.exception("could not change autostart")
        self.icon.update_menu()

    def _toggle_notifications(self, icon, item) -> None:
        self._set_pref("notifications", not self.cfg["notifications"])

    def _quit(self, icon, item) -> None:
        self.stop.set()
        self.wake.set()
        icon.stop()

    def _check_updates(self) -> None:
        latest = updates.latest_version()
        if latest is None:
            message = self.t("update_failed")
        elif updates.is_newer(latest):
            message = self.t("update_available", v=latest)
            webbrowser.open(updates.RELEASES_URL)
        else:
            message = self.t("up_to_date", v=__version__)
        self.icon.notify(message, self.t("title"))

    def _open_window(self, name: str, target: Callable) -> None:
        """Runs a tkinter window in its own thread; only one window of each kind at a time."""
        if name in self._open_windows:
            return
        self._open_windows.add(name)

        def run() -> None:
            try:
                target()
            except Exception:
                log.exception("%s window failed", name)
            finally:
                self._open_windows.discard(name)

        threading.Thread(target=run, daemon=True).start()

    def open_details(self) -> None:
        self._open_window("details", DetailsWindow(self, self.open_settings, self.wake.set).run)

    def open_settings(self) -> None:
        self._open_window("settings", lambda: show_settings(self.cfg, self.lang, self.on_saved))

    def on_saved(self, cfg: dict) -> None:
        self.cfg.update(cfg)
        self.snapshot.error = None
        self.backoff = 0.0
        self.wake.set()

    # ------------------------------------------------------------ data
    def refresh_once(self) -> None:
        snapshot = self.snapshot
        now = datetime.now(timezone.utc)
        try:
            if not is_configured(self.cfg):
                raise UsageError("err_setup")
            usage = fetch_usage(self.cfg)
            snapshot.usage, snapshot.updated, snapshot.error, self.backoff = usage, datetime.now(), None, 0.0
            self._notify(usage)
        except UsageError as e:
            snapshot.error = (e.key, e.arg)
            self.backoff = float(e.retry_after or 0)
            log.warning("fetch failed: %s %s", e.key, e.arg)
        except Exception as e:
            snapshot.error = ("err_generic", str(e)[:80])
            log.exception("unexpected error")
        try:
            snapshot.stats = self.local_stats.scan(now)
        except Exception:
            log.exception("local statistics failed")
        self._publish()

    def _notify(self, usage) -> None:
        if not self.cfg["notifications"]:
            return
        for alert in self.alerts.check(usage):
            try:
                self.icon.notify(self._alert_text(alert), self.t("title"))
            except Exception:
                log.exception("notification failed")

    def _alert_text(self, alert: Alert) -> str:
        name = self._limit_name(alert.limit)
        if alert.kind == "threshold":
            return self.t("n_threshold", name=name, p=f"{alert.value:.0f}")
        if alert.kind == "forecast":
            return self.t("n_forecast", name=name, t=duration(alert.value, units(self.lang)))
        return self.t("n_reset", name=name)

    def _publish(self) -> None:
        """Pushes the current snapshot to the icon, tooltip, menu and any open window."""
        self.version += 1
        snapshot = self.snapshot
        self.icon.icon = make_icon(snapshot.usage, self.cfg["icon_mode"], snapshot.stale)
        usage = snapshot.usage
        if usage:
            tip = self.t("tip_ok", s=f"{usage.session.pct:.0f}" if usage.session else "-",
                         w=f"{usage.weekly.pct:.0f}" if usage.weekly else "-")
            tip += self.t("tip_stale") if snapshot.error else ""
        elif snapshot.error:
            tip = self.t("tip_err", e=self._error_text())
        else:
            tip = self.t("title")
        self.icon.title = tip[:127]
        self.icon.update_menu()

    def _worker(self) -> None:
        while not self.stop.is_set():
            self.refresh_once()
            delay = poll_delay(self.cfg["interval_seconds"], self.snapshot.usage, datetime.now(timezone.utc),
                               self.backoff, random.uniform(0, JITTER_SECONDS))
            self.wake.wait(delay)
            self.wake.clear()

    def run(self) -> None:
        threading.Thread(target=self._worker, daemon=True).start()
        if not is_configured(self.cfg):  # first run: ask for the login right away
            self.open_settings()
        self.icon.run()
