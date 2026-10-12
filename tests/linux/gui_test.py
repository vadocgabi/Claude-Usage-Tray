"""Integration test: the real application in a real (virtual) Linux desktop session.

Run inside the test container (see run_tests.ps1 / run_tests.sh):
    python3 gui_test.py SCENARIO [SCREENSHOT_DIR]

Scenarios
    sni      D-Bus session + StatusNotifier host (snixembed, a third-party implementation) + tray
    xembed   X11 system tray only (no StatusNotifier watcher)       -> pystray XEmbed backend
    nowatch  session bus but no tray host at all                     -> details window is shown instead
    nobus    no session bus, no tray                                 -> details window is shown instead
    firstrun no Claude Code login and nothing configured             -> the settings window opens
"""
import http.server
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "sni"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/out")
OUT.mkdir(parents=True, exist_ok=True)
SRC = Path(os.environ.get("APP_SRC", "/src"))
APP_CMD = os.environ.get("APP_CMD", f"python3 {SRC}/claude_usage_tray.py").split()
DISPLAY = ":99"
API_PORT = 18765

results = []
procs = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition)))
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}" + (f"   {detail}" if detail and not condition else ""), flush=True)


def start(cmd, **kw) -> subprocess.Popen:
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kw)
    procs.append(p)
    return p


def wait_for(predicate, timeout=15.0, step=0.25):
    end = time.time() + timeout
    while time.time() < end:
        try:
            value = predicate()
            if value:
                return value
        except Exception:
            pass
        time.sleep(step)
    return None


# ---------------------------------------------------------------- fake Anthropic usage endpoint
USAGE = {"five_hour": 62.0, "seven_day": 41.0}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("Authorization") != "Bearer test-token" or "oauth-2025-04-20" not in str(
                self.headers.get("anthropic-beta")):
            self.send_response(401)
            self.end_headers()
            return
        now = time.time()
        iso = lambda delta: time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now + delta))
        body = json.dumps({
            "five_hour": {"utilization": USAGE["five_hour"], "resets_at": iso(2.5 * 3600)},
            "seven_day": {"utilization": USAGE["seven_day"], "resets_at": iso(3 * 86400)},
            "seven_day_sonnet": {"utilization": 28.0, "resets_at": iso(3 * 86400)},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main() -> int:
    home = Path(tempfile.mkdtemp(prefix="cut-home-"))
    runtime = Path(tempfile.mkdtemp(prefix="cut-run-"))
    runtime.chmod(0o700)
    (home / ".claude").mkdir()
    if SCENARIO != "firstrun":
        (home / ".claude" / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {
            "accessToken": "test-token", "expiresAt": int((time.time() + 86400) * 1000),
            "subscriptionType": "max", "rateLimitTier": "default_claude_max_5x"}}))
    env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), XDG_RUNTIME_DIR=str(runtime),
               CLAUDE_CONFIG_DIR=str(home / ".claude"), DISPLAY=DISPLAY, LANG="hu_HU.UTF-8", LC_ALL="hu_HU.UTF-8",
               CLAUDE_USAGE_TEST_API=f"http://127.0.0.1:{API_PORT}", PYTHONUNBUFFERED="1",
               GTK_THEME="Adwaita:dark")
    env.pop("DBUS_SESSION_BUS_ADDRESS", None)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", API_PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print(f"== scenario: {SCENARIO}", flush=True)
    start(["Xvfb", DISPLAY, "-screen", "0", "1280x800x24", "-nolisten", "tcp"], env=env)
    check("X server starts", wait_for(lambda: subprocess.run(["xdpyinfo", "-display", DISPLAY],
                                                             capture_output=True).returncode == 0))
    if SCENARIO != "nobus":
        address = subprocess.run(["dbus-daemon", "--session", "--fork", "--print-address"], env=env,
                                 capture_output=True, text=True, errors="replace").stdout.strip()
        env["DBUS_SESSION_BUS_ADDRESS"] = address
        check("session bus starts", bool(address))
        start(["dunst"], env=env)
    if SCENARIO in ("sni", "xembed", "firstrun"):
        start(["stalonetray", "--geometry", "6x1+1100+0", "--icon-size", "32", "--background", "#303040",
               "--grow-gravity", "NE"], env=env)
        time.sleep(1.0)
    if SCENARIO in ("sni", "firstrun"):
        start(["snixembed", "--fork"], env=env)
        time.sleep(1.0)

    log_file = open(OUT / f"app-{SCENARIO}.log", "w")
    app = subprocess.Popen(APP_CMD, env=env, stdout=log_file, stderr=subprocess.STDOUT, text=True)
    procs.append(app)
    time.sleep(1)
    check("application is running", app.poll() is None)

    def windows(pattern: str) -> list:
        out = subprocess.run(["xdotool", "search", "--name", pattern], env=env, capture_output=True, text=True, errors="replace")
        return [w for w in out.stdout.split() if w]

    def shot(name: str) -> None:
        subprocess.run(["import", "-display", DISPLAY, "-window", "root", str(OUT / f"{SCENARIO}-{name}.png")],
                       env=env, capture_output=True)

    def settings() -> dict:
        try:
            return json.loads((home / ".config" / "ClaudeUsageTray" / "settings.json").read_text())
        except (OSError, ValueError):
            return {}

    def app_log() -> str:
        return (home / ".config" / "ClaudeUsageTray" / "claude_usage_tray.log").read_text(errors="ignore") \
            if (home / ".config" / "ClaudeUsageTray" / "claude_usage_tray.log").exists() else ""

    # ------------------------------------------------------------ scenario specific checks
    if SCENARIO == "sni":
        from jeepney import DBusAddress, new_method_call
        from jeepney.io.blocking import open_dbus_connection
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = env["DBUS_SESSION_BUS_ADDRESS"]
        conn = open_dbus_connection(bus="SESSION")

        def call(address, member, sig="", body=(), timeout=5):
            return conn.send_and_get_reply(new_method_call(address, member, sig, body), timeout=timeout).body

        bus = DBusAddress("/org/freedesktop/DBus", bus_name="org.freedesktop.DBus", interface="org.freedesktop.DBus")

        def item_name():
            names = call(bus, "ListNames")[0]
            found = [n for n in names if n.startswith("org.kde.StatusNotifierItem-")]
            return found[0] if found else None

        name = wait_for(item_name, 20)
        check("tray item appears on the bus", name is not None)
        if name is None:
            return finish(app, env, home)
        item = DBusAddress("/StatusNotifierItem", bus_name=name, interface="org.freedesktop.DBus.Properties")
        menu = DBusAddress("/MenuBar", bus_name=name, interface="com.canonical.dbusmenu")

        # wait for the first successful fetch (title shows the percentages)
        def title():
            props = call(item, "GetAll", "s", ("org.kde.StatusNotifierItem",))[0]
            return props["Title"][1] if "62%" in props["Title"][1] else None

        got = wait_for(title, 25)
        check("title shows the fetched usage", got is not None, str(got))
        props = call(item, "GetAll", "s", ("org.kde.StatusNotifierItem",))[0]
        check("icon pixmaps are provided", len(props["IconPixmap"][1]) >= 4 and props["IconPixmap"][1][0][0] > 0)
        check("item is not menu-only (left click opens details)", props["ItemIsMenu"][1] is False)
        check("registered with the watcher (snixembed)", "registered with the StatusNotifierWatcher: True" in app_log())

        def layout():
            return call(menu, "GetLayout", "iias", (0, -1, []))[1]

        def labels(node, acc=None):
            acc = [] if acc is None else acc
            nid, props_, children = node
            if "label" in props_:
                acc.append((nid, props_["label"][1], props_))
            for _sig, child in children:
                labels(child, acc)
            return acc

        flat = labels(layout())
        by_label = {l: (i, p) for i, l, p in flat}
        texts = [l for _, l, _ in flat]
        check("menu has localized (Hungarian) entries", "Részletek" in texts and "Beállítások..." in texts, str(texts[:6]))
        check("menu shows live usage line", any("62%" in t for t in texts))
        check("menu shows model line", any("Sonnet 28%" in t for t in texts))

        # drive menu actions over D-Bus like a tray host does
        def click(label):
            call(menu, "Event", "isvu", (by_label[label][0], "clicked", ("s", ""), int(time.time())))

        click("Értesítések")
        check("toggle notifications is persisted", wait_for(lambda: settings().get("notifications") is False, 5))
        click("Indítás bejelentkezéskor")
        autostart = home / ".config" / "autostart" / "ClaudeUsageTray.desktop"
        check("autostart entry is written", wait_for(autostart.exists, 5))
        click("English")
        check("language change is persisted", wait_for(lambda: settings().get("language") == "en", 5))
        flat = labels(layout())
        check("menu is re-localized without restart", any(l == "Details" for _, l, _ in flat),
              str([l for _, l, _ in flat][:6]))

        # left click -> details window
        call(DBusAddress("/StatusNotifierItem", bus_name=name, interface="org.kde.StatusNotifierItem"),
             "Activate", "ii", (10, 10))
        win = wait_for(lambda: windows("Claude"), 10)
        check("left click opens the details window", bool(win))
        time.sleep(1.0)
        shot("details")

        # an alert: raise usage above the threshold, refresh, expect a desktop notification
        click("Értesítések")                                          # notifications back on
        wait_for(lambda: settings().get("notifications") is True, 5)
        USAGE["five_hour"] = 93.0
        flat = labels(layout())
        refresh_id = [i for i, l, _ in flat if l == "Refresh now"][0]
        call(menu, "Event", "isvu", (refresh_id, "clicked", ("s", ""), 0))
        time.sleep(3)
        def delivered() -> int:
            total = 0
            for what in ("displayed", "history"):
                out = subprocess.run(["dunstctl", "count", what], env=env, capture_output=True, text=True, errors="replace").stdout
                total += int(out.strip() or 0)
            return total

        check("threshold alert reaches the notification daemon", wait_for(lambda: delivered() >= 1, 8),
              f"delivered={delivered()}")
        shot("tray")

        # single instance
        second = subprocess.run(APP_CMD, env=env, capture_output=True, text=True, timeout=60)
        check("second instance exits immediately", second.returncode == 0)

        # quit through the menu
        quit_id = [i for i, l, _ in labels(layout()) if l == "Quit"][0]
        call(menu, "Event", "isvu", (quit_id, "clicked", ("s", ""), 0))
        check("quit from the menu stops the application", wait_for(lambda: app.poll() is not None, 10) is not None)
        return finish(app, env, home, quit_already=True)

    if SCENARIO == "xembed":
        ok = wait_for(lambda: "pystray" in app_log() or "XEmbed" in app_log(), 20)
        check("XEmbed backend is selected", "tray: XEmbed" in app_log(), app_log()[-300:])
        time.sleep(3)
        tree = subprocess.run(["xwininfo", "-display", DISPLAY, "-root", "-tree"], env=env, capture_output=True, errors="replace",
                              text=True).stdout
        check("tray icon window is embedded", re.search(r'"claude_usage"|"Claude', tree) is not None)
        shot("tray")
        return finish(app, env, home)

    if SCENARIO == "firstrun":
        win = wait_for(lambda: windows("Claude Usage Tray"), 20)
        check("settings window opens on first run", bool(win))
        time.sleep(1.0)
        shot("settings")
        names = subprocess.run(["xdotool", "getwindowname", win[0]], env=env, capture_output=True, text=True,
                               errors="replace").stdout if win else ""
        check("it is the settings window", "Beállítások" in names or "Settings" in names, names)
        return finish(app, env, home)

    if SCENARIO in ("nowatch", "nobus"):
        win = wait_for(lambda: windows("Claude"), 20)
        check("details window is shown when there is no tray", bool(win))
        time.sleep(1.0)
        shot("details")
        check("fallback is logged", "no system tray available" in app_log() or "tray: none" in app_log(), app_log()[-300:])
        return finish(app, env, home)
    return finish(app, env, home)


def finish(app, env, home, quit_already=False) -> int:
    if not quit_already and app.poll() is None:
        app.send_signal(signal.SIGTERM)
        try:
            app.wait(timeout=5)
        except subprocess.TimeoutExpired:
            app.kill()
    crash = Path(OUT / f"app-{SCENARIO}.log").read_text(errors="ignore") if (OUT / f"app-{SCENARIO}.log").exists() else ""
    check("no Python traceback on stdout/stderr", "Traceback" not in crash, crash[-400:])
    for p in procs:
        if p.poll() is None:
            p.terminate()
    failed = [n for n, ok in results if not ok]
    print(f"== {SCENARIO}: {len(results) - len(failed)}/{len(results)} checks passed", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
