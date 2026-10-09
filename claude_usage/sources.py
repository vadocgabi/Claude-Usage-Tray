"""Usage data sources: the Claude Code OAuth endpoint and the claude.ai session-cookie endpoint.

Both return the same `five_hour` / `seven_day` / per-model fields, so one parser serves both.
The OAuth token is only ever read, never refreshed: Claude Code owns it and rotating it here
could log Claude Code out.
"""
from __future__ import annotations

import ctypes
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

from . import __version__
from .config import has_cookie_login
from .model import SESSION_HOURS, WEEK_HOURS, Limit, Usage
from .paths import claude_dir

OAUTH_URL = "https://api.anthropic.com/api/oauth/usage"
OAUTH_BETA = "oauth-2025-04-20"
COOKIE_URL = "https://claude.ai/api/organizations/{org_id}/usage"
CREDENTIAL_TARGET = "Claude Code-credentials"  # Windows Credential Manager entry of Claude Code
MAX_BODY = 1_000_000
MAX_RETRY_AFTER = 3600
EXPIRY_SKEW_SECONDS = 60


class UsageError(Exception):
    """A failure that the UI translates: `key` selects the message, `arg` fills its placeholder."""

    def __init__(self, key: str, arg: str = "", retry_after: Optional[int] = None):
        super().__init__(key)
        self.key = key
        self.arg = arg
        self.retry_after = retry_after


# ---------------------------------------------------------------- OAuth credentials
@dataclass
class OAuthCredentials:
    token: str
    expires_at: Optional[datetime]
    plan: str

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        if self.expires_at is None:
            return False
        now = now or datetime.now(timezone.utc)
        return (self.expires_at - now).total_seconds() <= EXPIRY_SKEW_SECONDS


def plan_label(subscription_type: str, rate_tier: str) -> str:
    tier = (rate_tier or "").lower()
    kind = (subscription_type or "").lower()
    if "max_20x" in tier:
        return "Max 20x"
    if "max_5x" in tier:
        return "Max 5x"
    return kind.title() if kind else ""


def parse_credentials(text: str) -> Optional[OAuthCredentials]:
    """Parses Claude Code's credentials JSON (`{"claudeAiOauth": {...}}`)."""
    try:
        oauth = json.loads(text).get("claudeAiOauth") or {}
    except (ValueError, AttributeError):
        return None
    token = oauth.get("accessToken")
    if not token:
        return None
    expires_at = None
    raw = oauth.get("expiresAt")
    if isinstance(raw, (int, float)) and raw > 0:
        seconds = raw / 1000 if raw > 1e11 else raw  # milliseconds or seconds
        expires_at = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return OAuthCredentials(token, expires_at,
                            plan_label(oauth.get("subscriptionType", ""), oauth.get("rateLimitTier", "")))


class _Credential(ctypes.Structure):
    _fields_ = [("Flags", ctypes.c_uint32), ("Type", ctypes.c_uint32),
                ("TargetName", ctypes.c_wchar_p), ("Comment", ctypes.c_wchar_p),
                ("LastWritten", ctypes.c_uint32 * 2), ("BlobSize", ctypes.c_uint32),
                ("Blob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", ctypes.c_uint32),
                ("AttributeCount", ctypes.c_uint32), ("Attributes", ctypes.c_void_p),
                ("TargetAlias", ctypes.c_wchar_p), ("UserName", ctypes.c_wchar_p)]


def _credentials_from_manager() -> Optional[OAuthCredentials]:
    """Reads Claude Code's entry from the Windows Credential Manager, if present."""
    try:
        advapi32 = ctypes.windll.advapi32
        advapi32.CredReadW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                       ctypes.POINTER(ctypes.POINTER(_Credential))]
        advapi32.CredFree.argtypes = [ctypes.c_void_p]
        pointer = ctypes.POINTER(_Credential)()
        if not advapi32.CredReadW(CREDENTIAL_TARGET, 1, 0, ctypes.byref(pointer)):  # 1 = generic
            return None
        try:
            blob = bytes(pointer.contents.Blob[:pointer.contents.BlobSize])
        finally:
            advapi32.CredFree(pointer)
        for encoding in ("utf-8", "utf-16-le"):
            try:
                creds = parse_credentials(blob.decode(encoding))
            except UnicodeDecodeError:
                continue
            if creds:
                return creds
    except (OSError, AttributeError):
        pass
    return None


def _credentials_from_file(directory: Optional[Path] = None) -> Optional[OAuthCredentials]:
    path = (directory or claude_dir()) / ".credentials.json"
    try:
        return parse_credentials(path.read_text(encoding="utf-8"))
    except OSError:
        return None


def read_oauth_credentials() -> Optional[OAuthCredentials]:
    """Credential Manager first, then ~/.claude/.credentials.json."""
    return _credentials_from_manager() or _credentials_from_file()


# ---------------------------------------------------------------- parsing
def _bucket(node) -> Optional[tuple]:
    if isinstance(node, dict) and node.get("utilization") is not None:
        return float(node["utilization"]), node.get("resets_at")
    return None


def _scoped_models(data: dict) -> list:
    """Per-model weekly caps from the `limits` array (`kind == weekly_scoped`)."""
    found = []
    for item in data.get("limits") or []:
        if not isinstance(item, dict) or item.get("kind") != "weekly_scoped":
            continue
        model = (item.get("scope") or {}).get("model") or {}
        name = model.get("display_name") if isinstance(model, dict) else None
        if name and item.get("percent") is not None:
            found.append((str(name), float(item["percent"]), item.get("resets_at")))
    return found


def parse_usage(data: dict, source: str = "", plan: str = "") -> Usage:
    """Turns either endpoint's JSON into a `Usage`. Raises `UsageError('err_format')` if nothing usable."""
    if not isinstance(data, dict):
        raise UsageError("err_format")

    def pick(top_key: str, kind: str):
        found = _bucket(data.get(top_key))
        if found:
            return found
        for item in data.get("limits") or []:
            if isinstance(item, dict) and item.get("kind") == kind and item.get("percent") is not None:
                return float(item["percent"]), item.get("resets_at")
        return None

    usage = Usage(plan=plan, source=source)
    session, weekly = pick("five_hour", "session"), pick("seven_day", "weekly_all")
    if session:
        usage.session = Limit("session", "", session[0], session[1], SESSION_HOURS)
    if weekly:
        usage.weekly = Limit("weekly", "", weekly[0], weekly[1], WEEK_HOURS)
    if not (usage.session or usage.weekly):
        raise UsageError("err_format")

    named = [("Sonnet", _bucket(data.get("seven_day_sonnet"))), ("Opus", _bucket(data.get("seven_day_opus")))]
    named += [(name, (pct, reset)) for name, pct, reset in _scoped_models(data)]
    seen = set()
    for name, found in named:
        if found and name.lower() not in seen:
            seen.add(name.lower())
            usage.models.append(Limit(f"model:{name}", name, found[0], found[1], WEEK_HOURS))

    extra = data.get("extra_usage")
    if isinstance(extra, dict) and extra.get("is_enabled") and extra.get("utilization") is not None:
        usage.extra = Limit("extra", "", float(extra["utilization"]))

    rows = (data.get("seven_day_breakdown") or {}).get("rows") or []
    usage.breakdown = [(str(r.get("display_name") or r.get("key")), float(r["percent"]))
                       for r in rows if isinstance(r, dict) and r.get("percent")]  # zero shares are noise
    return usage


# ---------------------------------------------------------------- fetching
def _retry_after(raw: Optional[str]) -> int:
    """Retry-After as seconds (number or HTTP date), clamped to a sane range."""
    default = 600
    if not raw:
        return default
    try:
        seconds = int(raw.strip())
    except ValueError:
        try:
            when = parsedate_to_datetime(raw)
            when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
            seconds = int((when - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError):
            return default
    return max(30, min(seconds, MAX_RETRY_AFTER))


def _rate_error(raw_header: Optional[str]) -> UsageError:
    seconds = _retry_after(raw_header)
    return UsageError("err_rate", str(max(1, round(seconds / 60))), retry_after=seconds)


def fetch_oauth(creds: Optional[OAuthCredentials] = None) -> Usage:
    creds = creds or read_oauth_credentials()
    if creds is None:
        raise UsageError("err_oauth_missing")
    if creds.is_expired():
        raise UsageError("err_oauth_expired")
    request = urllib.request.Request(OAUTH_URL, headers={
        "Accept": "application/json",
        "Authorization": f"Bearer {creds.token}",
        "anthropic-beta": OAUTH_BETA,
        "User-Agent": f"claude-usage-tray/{__version__}",
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read(MAX_BODY)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise _rate_error(e.headers.get("Retry-After"))
        if e.code in (401, 403):
            raise UsageError("err_oauth_auth", str(e.code))
        raise UsageError("err_generic", f"HTTP {e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise UsageError("err_generic", str(getattr(e, "reason", e))[:80])
    try:
        return parse_usage(json.loads(body), "oauth", creds.plan)
    except ValueError:
        raise UsageError("err_format")


def fetch_cookie(cfg: dict) -> Usage:
    from curl_cffi import requests  # imported lazily: only the cookie mode needs it
    cookies = {"sessionKey": cfg["session_key"]}
    if cfg.get("cf_clearance"):
        cookies["cf_clearance"] = cfg["cf_clearance"]
    try:
        response = requests.get(
            COOKIE_URL.format(org_id=cfg["org_id"]), cookies=cookies, impersonate="chrome", timeout=20,
            headers={"accept": "*/*", "content-type": "application/json",
                     "anthropic-client-platform": "web_claude_ai",
                     "referer": "https://claude.ai/settings/usage"})
    except Exception as e:
        raise UsageError("err_generic", str(e)[:80])
    if response.status_code in (401, 403):
        raise UsageError("err_auth", str(response.status_code))
    if response.status_code == 429:
        raise _rate_error(response.headers.get("Retry-After"))
    if response.status_code != 200:
        raise UsageError("err_generic", f"HTTP {response.status_code}")
    try:
        return parse_usage(response.json(), "cookie")
    except ValueError:
        raise UsageError("err_format")


def available_methods(cfg: dict) -> list:
    """Methods that can be tried right now for the configured auth mode, in priority order."""
    mode = cfg.get("auth_mode", "auto")
    methods = []
    if mode in ("auto", "oauth") and read_oauth_credentials() is not None:
        methods.append("oauth")
    if mode in ("auto", "cookie") and has_cookie_login(cfg):
        methods.append("cookie")
    return methods


def is_configured(cfg: dict) -> bool:
    return bool(available_methods(cfg))


def fetch_usage(cfg: dict) -> Usage:
    """Fetches usage with the configured method(s); `auto` falls back from OAuth to the cookie."""
    methods = available_methods(cfg)
    if not methods:
        raise UsageError("err_oauth_missing" if cfg.get("auth_mode") == "oauth" else "err_setup")
    error = None
    for method in methods:
        try:
            return fetch_oauth() if method == "oauth" else fetch_cookie(cfg)
        except UsageError as e:
            if e.key == "err_rate":
                raise  # do not hit another endpoint while rate limited
            error = e
    raise error
