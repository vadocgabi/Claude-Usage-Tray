import sys
import time

sys.path.insert(0, "/src")
from claude_usage.tray.notifier import Notifier

notifier = Notifier()
print("via D-Bus:", notifier._via_dbus("Claude usage", "Current session: 93% reached"))
time.sleep(1)
