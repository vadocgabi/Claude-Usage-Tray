"""Configuration: credentials (config.json, secrets encrypted) and tray preferences (settings.json)."""
from __future__ import annotations

import json
from pathlib import Path

from . import dpapi
from .paths import CONFIG_PATH, SETTINGS_PATH

AUTH_MODES = ("auto", "oauth", "cookie")
ICON_MODES = ("both", "session")
INTERVALS = (60, 120, 300, 600, 900)  # seconds offered in the tray menu
MIN_INTERVAL = 60

DEFAULTS = {
    "auth_mode": "auto",
    "org_id": "",
    "session_key": "",
    "cf_clearance": "",
    "interval_seconds": 300,
    "icon_mode": "both",
    "language": "",
    "notifications": True,
    "notify_thresholds": [80, 90, 100],
}
CREDENTIAL_KEYS = ("auth_mode", "org_id", "session_key", "cf_clearance")
SECRET_KEYS = ("session_key", "cf_clearance")
PREFERENCE_KEYS = ("language", "notifications", "interval_seconds", "icon_mode")


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load_config(config_path: Path = CONFIG_PATH, settings_path: Path = SETTINGS_PATH) -> dict:
    """Defaults < config.json < settings.json, with secrets decrypted."""
    cfg = dict(DEFAULTS)
    cfg.update(_read_json(config_path))
    cfg.update({k: v for k, v in _read_json(settings_path).items() if k in PREFERENCE_KEYS})
    for key in SECRET_KEYS:
        cfg[key] = dpapi.decrypt(cfg.get(key, ""))
    if cfg["auth_mode"] not in AUTH_MODES:
        cfg["auth_mode"] = "auto"
    if cfg["icon_mode"] not in ICON_MODES:
        cfg["icon_mode"] = "both"
    cfg["interval_seconds"] = max(MIN_INTERVAL, int(cfg["interval_seconds"] or DEFAULTS["interval_seconds"]))
    return cfg


def save_credentials(cfg: dict, config_path: Path = CONFIG_PATH) -> None:
    """Writes only the credential keys, encrypting secrets; other keys in the file are kept."""
    stored = _read_json(config_path)
    for key in CREDENTIAL_KEYS:
        value = cfg.get(key, "")
        stored[key] = dpapi.encrypt(value) if key in SECRET_KEYS else value
    config_path.write_text(json.dumps(stored, indent=2), encoding="utf-8")


def save_preferences(cfg: dict, settings_path: Path = SETTINGS_PATH) -> None:
    try:
        prefs = {key: cfg[key] for key in PREFERENCE_KEYS if cfg.get(key) not in (None, "")}
        settings_path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    except OSError:
        pass


def has_cookie_login(cfg: dict) -> bool:
    return bool(cfg.get("org_id") and cfg.get("session_key"))
