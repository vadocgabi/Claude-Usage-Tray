"""Claude Usage Tray / Claude használat a Windows tálcán.

Shows claude.ai "Current session" and "This week" usage in the system tray.
A claude.ai "Current session" és "This week" használatát mutatja a tálcán.

Install / Telepítés:  pip install -r requirements.txt
Run / Indítás:        pythonw claude_usage_tray.py
Autostart:            right-click menu -> "Start with Windows" (or --autostart / --no-autostart)
Settings / Beállítások: right-click menu -> "Settings..." (org_id + sessionKey)
Language / Nyelv:     right-click the tray icon -> "Nyelv / Language"
"""
from __future__ import annotations

import base64
import ctypes
import json
import os
import re
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path

__version__ = "1.0.0"
AUTHOR = "Vadóc Gábor"
YEAR = 2026

FROZEN = getattr(sys, "frozen", False)
if FROZEN:  # exe: a konfig a felhasználó AppData mappájába kerül / config lives in AppData
    BASE = Path(os.environ.get("APPDATA", Path.home())) / "ClaudeUsageTray"
    BASE.mkdir(parents=True, exist_ok=True)
else:
    BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
SETTINGS_PATH = BASE / "settings.json"  # a menüben választott nyelv / chosen language
USAGE_PAGE = "https://claude.ai/settings/usage"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "ClaudeUsageTray"

# ---------------------------------------------------------------- nyelvek / languages
LANGS = {"hu": "Magyar", "en": "English"}

STRINGS = {
    "hu": {
        "title": "Claude használat",
        "loading": "Betöltés...",
        "session": "Aktuális munkamenet: {p}%  (visszaállás: {t})",
        "week": "Ezen a héten: {p}%  (visszaállás: {t})",
        "updated": "Frissítve: {t}",
        "no_data": "Még nincs adat",
        "error_suffix": "  – HIBA: {e}",
        "refresh": "Frissítés most",
        "open_page": "Usage oldal megnyitása",
        "language": "Nyelv / Language",
        "quit": "Kilépés",
        "credit": "Készítette: {a} - {y}",
        "tip_ok": "Munkamenet: {s}% | Hét: {w}%",
        "tip_stale": " (hiba, régi adat)",
        "tip_err": "Claude: {e}",
        "err_auth": "HTTP {e}: lejárt süti vagy Cloudflare-tiltás",
        "err_format": "Ismeretlen válaszformátum",
        "err_generic": "{e}",
        "autostart_on": "Autostart bekapcsolva.",
        "autostart_off": "Autostart kikapcsolva.",
        "settings": "Beállítások...",
        "autostart": "Indítás a Windows-szal",
        "err_setup": "Add meg az org_id-t és a sessionKey-t (Beállítások...)",
        "set_title": "Claude Usage Tray – Beállítások",
        "set_intro": "Add meg a claude.ai adataidat. A kulcs titkosítva (Windows DPAPI) kerül mentésre.",
        "set_org": "Szervezeti azonosító (org_id):",
        "set_key": "sessionKey süti:",
        "set_cf": "cf_clearance (opcionális):",
        "set_show": "Kulcs megjelenítése",
        "set_help": "Hol találom? (Usage oldal megnyitása)",
        "set_hint": "F12 → Network → a „usage” kérés URL-je tartalmazza az org_id-t; Application → Cookies → sessionKey.",
        "set_test": "Kipróbálás",
        "set_save": "Mentés",
        "set_cancel": "Mégse",
        "set_missing": "Az org_id és a sessionKey kötelező.",
        "set_testing": "Próbalekérés...",
        "set_test_ok": "Működik! Munkamenet: {s}%, hét: {w}%",
        "set_test_fail": "Hiba: {e}",
        "days": ["H", "K", "Sze", "Cs", "P", "Szo", "V"],
    },
    "en": {
        "title": "Claude usage",
        "loading": "Loading...",
        "session": "Current session: {p}%  (resets: {t})",
        "week": "This week: {p}%  (resets: {t})",
        "updated": "Updated: {t}",
        "no_data": "No data yet",
        "error_suffix": "  – ERROR: {e}",
        "refresh": "Refresh now",
        "open_page": "Open Usage page",
        "language": "Nyelv / Language",
        "quit": "Quit",
        "credit": "Created by: {a} - {y}",
        "tip_ok": "Session: {s}% | Week: {w}%",
        "tip_stale": " (error, old data)",
        "tip_err": "Claude: {e}",
        "err_auth": "HTTP {e}: expired cookie or Cloudflare block",
        "err_format": "Unknown response format",
        "err_generic": "{e}",
        "autostart_on": "Autostart enabled.",
        "autostart_off": "Autostart disabled.",
        "settings": "Settings...",
        "autostart": "Start with Windows",
        "err_setup": "Enter org_id and sessionKey (Settings...)",
        "set_title": "Claude Usage Tray – Settings",
        "set_intro": "Enter your claude.ai details. The key is stored encrypted (Windows DPAPI).",
        "set_org": "Organization ID (org_id):",
        "set_key": "sessionKey cookie:",
        "set_cf": "cf_clearance (optional):",
        "set_show": "Show key",
        "set_help": "Where do I find it? (open Usage page)",
        "set_hint": "F12 → Network → the “usage” request URL contains the org_id; Application → Cookies → sessionKey.",
        "set_test": "Test",
        "set_save": "Save",
        "set_cancel": "Cancel",
        "set_missing": "org_id and sessionKey are required.",
        "set_testing": "Testing...",
        "set_test_ok": "Works! Session: {s}%, week: {w}%",
        "set_test_fail": "Error: {e}",
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    },
}


def credit_text(lang: str) -> str:
    return f"v{__version__} – " + STRINGS[lang]["credit"].format(a=AUTHOR, y=YEAR)


def detect_system_language() -> str:
    """Magyar Windows-felület esetén 'hu', különben 'en'."""
    try:
        import ctypes
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "hu" if (lang_id & 0x3FF) == 0x0E else "en"
    except Exception:
        return "en"


def load_language(cfg: dict | None = None) -> str:
    """Sorrend: settings.json (menüből választott) -> config.json 'language' -> rendszernyelv."""
    try:
        lang = json.loads(SETTINGS_PATH.read_text(encoding="utf-8")).get("language")
        if lang in LANGS:
            return lang
    except Exception:
        pass
    if cfg and cfg.get("language") in LANGS:
        return cfg["language"]
    return detect_system_language()


def save_language(lang: str) -> None:
    try:
        SETTINGS_PATH.write_text(json.dumps({"language": lang}, indent=2), encoding="utf-8")
    except OSError:
        pass


# ---------------------------------------------------------------- autostart
def autostart_command() -> str:
    if FROZEN:
        return f'"{sys.executable}"'
    pyw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pyw}" "{Path(__file__).resolve()}"'


def get_autostart() -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(enable: bool) -> None:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


if "--autostart" in sys.argv or "--no-autostart" in sys.argv:
    _enable = "--autostart" in sys.argv
    set_autostart(_enable)
    print(STRINGS[load_language()]["autostart_on" if _enable else "autostart_off"])
    sys.exit(0)


# ---------------------------------------------------------------- egy példány / single instance
_mutex = None


def already_running() -> bool:
    global _mutex
    try:
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\ClaudeUsageTray_SingleInstance")
        return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return False


import pystray
from curl_cffi import requests
from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------- titkosítás / DPAPI
class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    buf = ctypes.create_string_buffer(data, len(data))
    inp = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    out = _Blob()
    crypt = ctypes.windll.crypt32
    fn = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    if not fn(ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI error")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


def encrypt_secret(text: str) -> str:
    if not text:
        return ""
    return "dpapi:" + base64.b64encode(_dpapi(text.encode("utf-8"), True)).decode("ascii")


def decrypt_secret(text: str) -> str:
    if text and text.startswith("dpapi:"):
        try:
            return _dpapi(base64.b64decode(text[6:]), False).decode("utf-8")
        except Exception:
            return ""
    return text or ""  # régi, titkosítatlan config is működik / plain legacy value


SECRET_FIELDS = ("session_key", "cf_clearance")


def load_config() -> dict:
    cfg = {"org_id": "", "session_key": "", "cf_clearance": "",
           "interval_seconds": 60, "icon_mode": "both"}
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    for f in SECRET_FIELDS:
        cfg[f] = decrypt_secret(cfg.get(f, ""))
    return cfg


def save_config(cfg: dict) -> None:
    out = dict(cfg)
    for f in SECRET_FIELDS:
        out[f] = encrypt_secret(out.get(f, ""))
    CONFIG_PATH.write_text(json.dumps(out, indent=2), encoding="utf-8")


def is_configured(cfg: dict) -> bool:
    return bool(cfg.get("org_id") and cfg.get("session_key"))


# ---------------------------------------------------------------- adatlekérés / fetching
class UsageError(Exception):
    """Hiba, amit a megjelenítéskor az aktuális nyelven írunk ki."""

    def __init__(self, key: str, arg: str = ""):
        super().__init__(key)
        self.key = key
        self.arg = arg


def fetch_usage(cfg: dict) -> dict:
    cookies = {"sessionKey": cfg["session_key"]}
    if cfg.get("cf_clearance"):
        cookies["cf_clearance"] = cfg["cf_clearance"]
    r = requests.get(
        f"https://claude.ai/api/organizations/{cfg['org_id']}/usage",
        cookies=cookies,
        headers={
            "accept": "*/*",
            "content-type": "application/json",
            "anthropic-client-platform": "web_claude_ai",
            "referer": "https://claude.ai/settings/usage",
        },
        impersonate="chrome",
        timeout=20,
    )
    if r.status_code in (401, 403):
        raise UsageError("err_auth", str(r.status_code))
    r.raise_for_status()
    data = r.json()

    def pick(top_key, kind):
        node = data.get(top_key)
        if isinstance(node, dict) and node.get("utilization") is not None:
            return node["utilization"], node.get("resets_at")
        for lim in data.get("limits") or []:
            if lim.get("kind") == kind:
                return lim.get("percent"), lim.get("resets_at")
        return None, None

    s_pct, s_reset = pick("five_hour", "session")
    w_pct, w_reset = pick("seven_day", "weekly_all")
    if s_pct is None and w_pct is None:
        raise UsageError("err_format")
    rnd = lambda v: None if v is None else int(round(v))
    return {"s": rnd(s_pct), "s_reset": s_reset, "w": rnd(w_pct), "w_reset": w_reset}


def local_time(iso: str | None, with_day: bool, days: list) -> str:
    if not iso:
        return "?"
    dt = datetime.fromisoformat(iso).astimezone()
    if with_day:
        return f"{days[dt.weekday()]} {dt:%H:%M}"
    return f"{dt:%H:%M}"


# ---------------------------------------------------------------- ikonrajzolás / icon
def colour(p):
    if p is None:
        return (90, 90, 90)
    if p >= 90:
        return (200, 40, 40)
    if p >= 70:
        return (225, 130, 0)
    return (37, 99, 235)


def font(size):
    for name in ("arialbd.ttf", "segoeuib.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_icon(state: dict | None, mode: str) -> Image.Image:
    S = 64
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if state is None:
        d.rounded_rectangle((0, 0, S - 1, S - 1), 12, fill=(90, 90, 90))
        d.text((S / 2, S / 2), "!", font=font(48), fill="white", anchor="mm")
        return img

    def label(p):
        return "--" if p is None else str(int(round(p)))

    if mode == "session":
        d.rounded_rectangle((0, 0, S - 1, S - 1), 12, fill=colour(state["s"]))
        t = label(state["s"])
        d.text((S / 2, S / 2), t, font=font(44 if len(t) < 3 else 34), fill="white", anchor="mm")
    else:  # both: felül session, alul hét / top: session, bottom: week
        d.rounded_rectangle((0, 0, S - 1, S // 2 - 1), 8, fill=colour(state["s"]))
        d.rounded_rectangle((0, S // 2, S - 1, S - 1), 8, fill=colour(state["w"]))
        for i, key in enumerate(("s", "w")):
            t = label(state[key])
            d.text((S / 2, S / 4 + i * S / 2), t,
                   font=font(30 if len(t) < 3 else 24), fill="white", anchor="mm")
    return img


# ---------------------------------------------------------------- beállító ablak / settings dialog
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")


def show_settings(cfg: dict, lang: str, on_saved) -> None:
    """Tkinter ablak; saját szálból hívandó / call from its own thread."""
    import tkinter as tk
    from tkinter import ttk

    T = lambda k, **kw: STRINGS[lang][k].format(**kw)
    root = tk.Tk()
    root.title(T("set_title"))
    root.resizable(False, False)
    root.attributes("-topmost", True)
    frm = ttk.Frame(root, padding=14)
    frm.grid()

    ttk.Label(frm, text=T("set_intro"), wraplength=440).grid(columnspan=2, sticky="w", pady=(0, 10))
    org, key, cf = (tk.StringVar(value=cfg["org_id"]), tk.StringVar(value=cfg["session_key"]),
                    tk.StringVar(value=cfg["cf_clearance"]))
    rows = (("set_org", org, ""), ("set_key", key, "*"), ("set_cf", cf, "*"))
    entries = []
    for i, (lab, var, mask) in enumerate(rows, start=1):
        ttk.Label(frm, text=T(lab)).grid(row=i, column=0, sticky="w", pady=3)
        e = ttk.Entry(frm, textvariable=var, width=52, show=mask)
        e.grid(row=i, column=1, pady=3, padx=(8, 0))
        entries.append(e)

    shown = tk.BooleanVar(value=False)

    def toggle():
        for e in entries[1:]:
            e.configure(show="" if shown.get() else "*")

    ttk.Checkbutton(frm, text=T("set_show"), variable=shown, command=toggle).grid(
        row=4, column=1, sticky="w", padx=(8, 0))
    link = ttk.Label(frm, text=T("set_help"), foreground="#2563eb", cursor="hand2")
    link.grid(row=5, columnspan=2, sticky="w", pady=(8, 0))
    link.bind("<Button-1>", lambda ev: webbrowser.open(USAGE_PAGE))
    ttk.Label(frm, text=T("set_hint"), wraplength=440, foreground="#666").grid(
        row=6, columnspan=2, sticky="w", pady=(2, 8))
    status = tk.StringVar()
    ttk.Label(frm, textvariable=status, wraplength=440).grid(row=7, columnspan=2, sticky="w")
    ttk.Label(frm, text=credit_text(lang), foreground="#888").grid(row=8, column=0, sticky="w", pady=(10, 0))

    def collect():
        m = UUID_RE.search(org.get())  # akár a teljes URL is beilleszthető / full URL may be pasted
        k = key.get().strip().strip('"')
        if k.lower().startswith("sessionkey="):
            k = k.split("=", 1)[1]
        new = dict(cfg, org_id=m.group(0) if m else org.get().strip(),
                   session_key=k, cf_clearance=cf.get().strip())
        return new if is_configured(new) else None

    def test():
        new = collect()
        if not new:
            status.set(T("set_missing"))
            return
        status.set(T("set_testing"))
        root.update_idletasks()
        try:
            r = fetch_usage(new)
            status.set(T("set_test_ok", s=r["s"], w=r["w"]))
        except UsageError as e:
            status.set(T("set_test_fail", e=T(e.key, e=e.arg)))
        except Exception as e:
            status.set(T("set_test_fail", e=str(e)[:150]))

    def save():
        new = collect()
        if not new:
            status.set(T("set_missing"))
            return
        save_config(new)
        root.destroy()
        on_saved(new)

    btns = ttk.Frame(frm)
    btns.grid(row=8, column=1, sticky="e", pady=(10, 0))
    ttk.Button(btns, text=T("set_test"), command=test).grid(row=0, column=0, padx=4)
    ttk.Button(btns, text=T("set_save"), command=save).grid(row=0, column=1, padx=4)
    ttk.Button(btns, text=T("set_cancel"), command=root.destroy).grid(row=0, column=2, padx=4)

    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    root.geometry(f"+{(root.winfo_screenwidth() - w) // 2}+{(root.winfo_screenheight() - h) // 3}")
    root.mainloop()


# ---------------------------------------------------------------- alkalmazás / app
class App:
    def __init__(self):
        self.cfg = load_config()
        self.lang = load_language(self.cfg)
        self.state = None
        self.error = None  # (kulcs, argumentum) – nyelvváltáskor újrafordítható
        self.updated = None
        self.wake = threading.Event()
        self.stop = threading.Event()
        self.settings_open = False
        if not is_configured(self.cfg):
            self.error = ("err_setup", "")

        def lang_item(code):
            # pystray csak 2 paraméteres hívhatót fogad el, ezért zárvány, nem alapértelmezett arg.
            return pystray.MenuItem(
                LANGS[code],
                lambda icon, item: self.set_language(code),
                checked=lambda item: self.lang == code,
                radio=True,
            )

        self.icon = pystray.Icon(
            "claude_usage", make_icon(None, self.cfg["icon_mode"]), self.t("title"),
            menu=pystray.Menu(
                pystray.MenuItem(lambda i: self.line_session(), None, enabled=False),
                pystray.MenuItem(lambda i: self.line_week(), None, enabled=False),
                pystray.MenuItem(lambda i: self.line_updated(), None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(lambda i: self.t("refresh"), self.on_refresh, default=True),
                pystray.MenuItem(lambda i: self.t("open_page"),
                                 lambda i, it: webbrowser.open(USAGE_PAGE)),
                pystray.MenuItem(lambda i: self.t("settings"), self.on_settings),
                pystray.MenuItem(lambda i: self.t("autostart"), self.on_autostart,
                                 checked=lambda item: get_autostart()),
                pystray.MenuItem(lambda i: self.t("language"),
                                 pystray.Menu(*[lang_item(c) for c in LANGS])),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(lambda i: credit_text(self.lang), None, enabled=False),
                pystray.MenuItem(lambda i: self.t("quit"), self.on_quit),
            ),
        )

    # fordítás / translation
    def t(self, key: str, **kw) -> str:
        return STRINGS[self.lang][key].format(**kw)

    def error_text(self) -> str:
        key, arg = self.error
        return self.t(key, e=arg)

    # menüsorok / menu lines
    def line_session(self):
        if not self.state:
            return self.error_text() if self.error else self.t("loading")
        days = STRINGS[self.lang]["days"]
        return self.t("session", p=self.state["s"],
                      t=local_time(self.state["s_reset"], False, days))

    def line_week(self):
        if not self.state:
            return "–"
        days = STRINGS[self.lang]["days"]
        return self.t("week", p=self.state["w"],
                      t=local_time(self.state["w_reset"], True, days))

    def line_updated(self):
        base = (self.t("updated", t=f"{self.updated:%H:%M:%S}")
                if self.updated else self.t("no_data"))
        if self.error and self.state:
            base += self.t("error_suffix", e=self.error_text())
        return base

    # műveletek / actions
    def on_refresh(self, icon, item):
        self.wake.set()

    def on_autostart(self, icon, item):
        try:
            set_autostart(not get_autostart())
        except OSError:
            pass
        self.icon.update_menu()

    def on_settings(self, icon=None, item=None):
        if self.settings_open:
            return
        self.settings_open = True

        def run():
            try:
                show_settings(self.cfg, self.lang, self.on_saved)
            finally:
                self.settings_open = False

        threading.Thread(target=run, daemon=True).start()

    def on_saved(self, cfg: dict):
        self.cfg = cfg
        self.error = None
        self.wake.set()

    def on_quit(self, icon, item):
        self.stop.set()
        self.wake.set()
        icon.stop()

    def set_language(self, code: str):
        self.lang = code
        save_language(code)
        self.update_ui()

    def update_ui(self):
        self.icon.icon = make_icon(self.state, self.cfg["icon_mode"])
        if self.state:
            tip = self.t("tip_ok", s=self.state["s"], w=self.state["w"])
            if self.error:
                tip += self.t("tip_stale")
        elif self.error:
            tip = self.t("tip_err", e=self.error_text())
        else:
            tip = self.t("title")
        self.icon.title = tip[:127]
        self.icon.update_menu()

    def refresh_once(self):
        if not is_configured(self.cfg):
            self.error = ("err_setup", "")
            self.update_ui()
            return
        try:
            self.state = fetch_usage(self.cfg)
            self.error = None
            self.updated = datetime.now()
        except UsageError as e:  # az utolsó jó érték megmarad / last good value is kept
            self.error = (e.key, e.arg)
        except Exception as e:
            self.error = ("err_generic", str(e)[:80])
        self.update_ui()

    def worker(self):
        while not self.stop.is_set():
            self.refresh_once()
            self.wake.wait(max(15, int(self.cfg["interval_seconds"])))
            self.wake.clear()

    def run(self):
        threading.Thread(target=self.worker, daemon=True).start()
        if not is_configured(self.cfg):  # első indítás / first run
            self.on_settings()
        self.icon.run()


if __name__ == "__main__":
    if already_running():
        sys.exit(0)
    App().run()
