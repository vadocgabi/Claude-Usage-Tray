#!/bin/bash
# Secrets go to the desktop keyring (gnome-keyring over the Secret Service API) and come back out.
set -u
export HOME=/tmp/kh XDG_CONFIG_HOME=/tmp/kh/.config XDG_RUNTIME_DIR=/tmp/kr DISPLAY=:99
mkdir -p "$HOME" "$XDG_RUNTIME_DIR" && chmod 700 "$XDG_RUNTIME_DIR"
eval "$(dbus-launch --sh-syntax)"
echo "" | gnome-keyring-daemon --unlock --components=secrets >/dev/null 2>&1
sleep 1
cd /src
python3 - <<'PY'
import json, sys
sys.path.insert(0, "/src")
from pathlib import Path
from claude_usage.config import load_config, save_credentials
from claude_usage.system import linux
backend = linux._keyring()
print("keyring backend:", type(backend.get_keyring()).__name__ if backend else None)
cfg = Path("/tmp/kh/config.json"); settings = Path("/tmp/kh/settings.json")
save_credentials({"auth_mode": "cookie", "org_id": "org-1", "session_key": "sk-ant-secret-value", "cf_clearance": ""}, cfg)
stored = json.loads(cfg.read_text())
print("stored session_key field:", stored["session_key"])
assert "sk-ant-secret-value" not in cfg.read_text(), "secret leaked into config.json"
assert stored["session_key"] == "keyring:session_key"
loaded = load_config(cfg, settings)
assert loaded["session_key"] == "sk-ant-secret-value", loaded["session_key"]
import os, stat
mode = stat.S_IMODE(os.stat(cfg).st_mode)
print("config.json mode:", oct(mode))
assert mode == 0o600
print("KEYRING OK")
PY
