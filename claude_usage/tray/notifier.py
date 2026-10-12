"""Desktop notifications on Linux: org.freedesktop.Notifications over D-Bus, `notify-send` as fallback."""
from __future__ import annotations

import logging
import shutil
import subprocess
import threading

log = logging.getLogger("claude_usage")

DEFAULT_TIMEOUT_MS = 8000


class Notifier:
    """Fire-and-forget; never raises and never blocks the caller."""

    def __init__(self, app_name: str = "Claude Usage Tray", icon: str = "claude-usage-tray"):
        self.app_name, self.icon = app_name, icon

    def send(self, title: str, message: str) -> None:
        threading.Thread(target=self._send, args=(title, message), daemon=True).start()

    def _send(self, title: str, message: str) -> None:
        if self._via_dbus(title, message):
            return
        if shutil.which("notify-send"):
            try:
                subprocess.run(["notify-send", "--app-name", self.app_name, "--icon", self.icon,
                                title, message], timeout=5, capture_output=True)
                return
            except (OSError, subprocess.SubprocessError):
                pass
        log.info("notification not delivered (no notification service): %s", message)

    def _via_dbus(self, title: str, message: str) -> bool:
        try:
            from jeepney import DBusAddress, new_method_call
            from jeepney.io.blocking import open_dbus_connection
            address = DBusAddress("/org/freedesktop/Notifications", bus_name="org.freedesktop.Notifications",
                                  interface="org.freedesktop.Notifications")
            call = new_method_call(address, "Notify", "susssasa{sv}i",
                                   (self.app_name, 0, self.icon, title, message, [], {}, DEFAULT_TIMEOUT_MS))
            with open_dbus_connection(bus="SESSION") as connection:
                connection.send_and_get_reply(call, timeout=3)
            return True
        except Exception:
            return False
