"""Hungarian / English UI strings and language selection."""
from __future__ import annotations

import ctypes

from . import AUTHOR, YEAR, __version__

LANGS = {"hu": "Magyar", "en": "English"}
HUNGARIAN_LANGID = 0x0E

STRINGS = {
    "hu": {
        # tray
        "title": "Claude használat",
        "loading": "Betöltés...",
        "session": "Aktuális munkamenet: {p}%  (visszaállás: {t})",
        "week": "Ezen a héten: {p}%  (visszaállás: {t})",
        "models_line": "Modellek: {m}",
        "updated": "Frissítve: {t}",
        "no_data": "Még nincs adat",
        "error_suffix": "  – HIBA: {e}",
        "details": "Részletek",
        "refresh": "Frissítés most",
        "open_page": "Usage oldal megnyitása",
        "settings": "Beállítások...",
        "autostart": "Indítás a Windows-szal",
        "notifications": "Értesítések",
        "interval": "Frissítési időköz",
        "minutes": "{n} perc",
        "icon_mode": "Ikon megjelenítése",
        "icon_both": "Két sáv (munkamenet + hét)",
        "icon_session": "Csak munkamenet",
        "icon_weekly": "Csak heti",
        "language": "Nyelv / Language",
        "check_updates": "Frissítések keresése",
        "update_available": "Új verzió érhető el: {v}",
        "up_to_date": "A program naprakész (v{v}).",
        "update_failed": "A frissítések keresése nem sikerült.",
        "quit": "Kilépés",
        "credit": "Készítette: {a} - {y}",
        "tip_ok": "Munkamenet: {s}% | Hét: {w}%",
        "tip_stale": " (hiba, régi adat)",
        "tip_err": "Claude: {e}",
        # notifications
        "n_threshold": "{name}: {p}% elérve",
        "n_forecast": "{name}: ilyen tempóval kb. {t} múlva eléred a limitet.",
        "n_reset": "{name}: visszaállt, újra használhatod.",
        # errors
        "err_setup": "Nincs bejelentkezés: add meg a Beállításokban (vagy jelentkezz be a Claude Code-ba)",
        "err_auth": "HTTP {e}: lejárt süti vagy Cloudflare-tiltás",
        "err_format": "Ismeretlen válaszformátum",
        "err_generic": "{e}",
        "err_rate": "Túl sok kérés, újrapróbálás {e} perc múlva",
        "err_oauth_missing": "A Claude Code bejelentkezése nem található",
        "err_oauth_expired": "A Claude Code tokenje lejárt – nyisd meg a Claude Code-ot, és frissül",
        "err_oauth_auth": "HTTP {e}: a Claude Code tokenjét elutasították",
        "autostart_on": "Autostart bekapcsolva.",
        "autostart_off": "Autostart kikapcsolva.",
        # details flyout
        "d_session": "Aktuális munkamenet",
        "d_week": "Heti használat",
        "d_extra": "Extra használat",
        "d_model": "Heti – {m}",
        "d_resets": "Visszaáll {t} múlva ({at})",
        "d_pace": "az időablak {p}%-a telt el",
        "d_eta": "Ilyen tempóval {t} múlva eléred a limitet",
        "d_breakdown": "Heti használat megoszlása",
        "d_tokens": "Claude Code tokenek (helyi napló)",
        "d_tokens_line": "Ma: {today}  ·  7 nap: {week}",
        "d_stale": "régi adat",
        "src_oauth": "Forrás: Claude Code (OAuth)",
        "src_cookie": "Forrás: claude.ai (süti)",
        # settings window
        "set_title": "Claude Usage Tray – Beállítások",
        "set_title_short": "Beállítások",
        "set_intro": "Válaszd ki, hogyan olvassa a program a használati adatokat. Mindkét mód ugyanazt mutatja.",
        "set_method": "Hitelesítés",
        "mode_auto": "Automatikus (OAuth, ha nincs, akkor süti)",
        "mode_oauth": "Claude Code bejelentkezés (OAuth) – nem kell semmit megadni",
        "mode_cookie": "claude.ai süti (sessionKey + org_id)",
        "set_oauth_found": "Claude Code bejelentkezés megtalálva{plan}.",
        "set_oauth_missing": "Claude Code bejelentkezés nem található – jelentkezz be a Claude Code-ba, vagy használd a sütit.",
        "set_cookie_title": "claude.ai süti",
        "set_org": "Szervezeti azonosító (org_id)",
        "set_key": "sessionKey süti",
        "set_cf": "cf_clearance (opcionális)",
        "set_show": "Kulcsok megjelenítése",
        "set_help": "Hol találom? (Usage oldal megnyitása)",
        "set_hint": "F12 → Network → a „usage” kérés URL-je tartalmazza az org_id-t; Application → Cookies → sessionKey. A kulcsot a program titkosítva (Windows DPAPI) menti.",
        "set_test": "Kipróbálás",
        "set_save": "Mentés",
        "set_cancel": "Mégse",
        "set_missing": "Nincs használható bejelentkezés a kiválasztott módhoz.",
        "set_testing": "Próbalekérés...",
        "set_test_ok": "Működik! Munkamenet: {s}%, hét: {w}%  ({src})",
        "set_test_fail": "Hiba: {e}",
        "days": ["H", "K", "Sze", "Cs", "P", "Szo", "V"],
    },
    "en": {
        # tray
        "title": "Claude usage",
        "loading": "Loading...",
        "session": "Current session: {p}%  (resets: {t})",
        "week": "This week: {p}%  (resets: {t})",
        "models_line": "Models: {m}",
        "updated": "Updated: {t}",
        "no_data": "No data yet",
        "error_suffix": "  – ERROR: {e}",
        "details": "Details",
        "refresh": "Refresh now",
        "open_page": "Open Usage page",
        "settings": "Settings...",
        "autostart": "Start with Windows",
        "notifications": "Notifications",
        "interval": "Refresh interval",
        "minutes": "{n} min",
        "icon_mode": "Icon style",
        "icon_both": "Two bars (session + week)",
        "icon_session": "Session only",
        "icon_weekly": "Weekly only",
        "language": "Nyelv / Language",
        "check_updates": "Check for updates",
        "update_available": "New version available: {v}",
        "up_to_date": "You are up to date (v{v}).",
        "update_failed": "Could not check for updates.",
        "quit": "Quit",
        "credit": "Created by: {a} - {y}",
        "tip_ok": "Session: {s}% | Week: {w}%",
        "tip_stale": " (error, old data)",
        "tip_err": "Claude: {e}",
        # notifications
        "n_threshold": "{name}: {p}% reached",
        "n_forecast": "{name}: at this pace you will hit the limit in about {t}.",
        "n_reset": "{name}: reset, you can use Claude again.",
        # errors
        "err_setup": "Not signed in: add your login in Settings (or sign in to Claude Code)",
        "err_auth": "HTTP {e}: expired cookie or Cloudflare block",
        "err_format": "Unknown response format",
        "err_generic": "{e}",
        "err_rate": "Rate limited, retrying in {e} min",
        "err_oauth_missing": "Claude Code sign-in not found",
        "err_oauth_expired": "The Claude Code token expired – open Claude Code and it will refresh",
        "err_oauth_auth": "HTTP {e}: the Claude Code token was rejected",
        "autostart_on": "Autostart enabled.",
        "autostart_off": "Autostart disabled.",
        # details flyout
        "d_session": "Current session",
        "d_week": "Weekly usage",
        "d_extra": "Extra usage",
        "d_model": "Weekly – {m}",
        "d_resets": "Resets in {t} ({at})",
        "d_pace": "{p}% of the window has elapsed",
        "d_eta": "At this pace you will hit the limit in {t}",
        "d_breakdown": "Weekly usage breakdown",
        "d_tokens": "Claude Code tokens (local logs)",
        "d_tokens_line": "Today: {today}  ·  7 days: {week}",
        "d_stale": "stale data",
        "src_oauth": "Source: Claude Code (OAuth)",
        "src_cookie": "Source: claude.ai (cookie)",
        # settings window
        "set_title": "Claude Usage Tray – Settings",
        "set_title_short": "Settings",
        "set_intro": "Choose how the app reads your usage. Both methods show the same data.",
        "set_method": "Authentication",
        "mode_auto": "Automatic (OAuth if available, otherwise cookie)",
        "mode_oauth": "Claude Code sign-in (OAuth) – nothing to enter",
        "mode_cookie": "claude.ai cookie (sessionKey + org_id)",
        "set_oauth_found": "Claude Code sign-in found{plan}.",
        "set_oauth_missing": "Claude Code sign-in not found – sign in to Claude Code, or use the cookie.",
        "set_cookie_title": "claude.ai cookie",
        "set_org": "Organization ID (org_id)",
        "set_key": "sessionKey cookie",
        "set_cf": "cf_clearance (optional)",
        "set_show": "Show keys",
        "set_help": "Where do I find it? (open Usage page)",
        "set_hint": "F12 → Network → the “usage” request URL contains the org_id; Application → Cookies → sessionKey. The key is stored encrypted (Windows DPAPI).",
        "set_test": "Test",
        "set_save": "Save",
        "set_cancel": "Cancel",
        "set_missing": "No usable sign-in for the selected method.",
        "set_testing": "Testing...",
        "set_test_ok": "Works! Session: {s}%, week: {w}%  ({src})",
        "set_test_fail": "Error: {e}",
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    },
}
UNITS = {"hu": ("n", "ó", "p"), "en": ("d", "h", "m")}


def tr(lang: str, key: str, **kwargs) -> str:
    table = STRINGS.get(lang) or STRINGS["en"]
    return table.get(key, STRINGS["en"].get(key, key)).format(**kwargs)


def units(lang: str) -> tuple:
    return UNITS.get(lang, UNITS["en"])


def credit_text(lang: str) -> str:
    return f"v{__version__} – " + tr(lang, "credit", a=AUTHOR, y=YEAR)


def detect_system_language() -> str:
    """'hu' on a Hungarian Windows UI, otherwise 'en'."""
    try:
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "hu" if (lang_id & 0x3FF) == HUNGARIAN_LANGID else "en"
    except (OSError, AttributeError):
        return "en"


def resolve_language(chosen: str) -> str:
    return chosen if chosen in LANGS else detect_system_language()
