#!/bin/bash
# Sends one notification through our Notifier and shows what the notification daemon (dunst) received.
export DISPLAY=:99 HOME=/tmp/h XDG_RUNTIME_DIR=/tmp/r
mkdir -p "$HOME" "$XDG_RUNTIME_DIR" && chmod 700 "$XDG_RUNTIME_DIR"
Xvfb :99 -screen 0 800x600x24 >/dev/null 2>&1 &
sleep 1
eval "$(dbus-launch --sh-syntax)"
dunst >/tmp/dunst.log 2>&1 &
sleep 1.5
python3 /src/tests/linux/notify_probe.py
echo "--- displayed: $(dunstctl count displayed)  history: $(dunstctl count history)  waiting: $(dunstctl count waiting)"
echo "--- history"
dunstctl history | head -40
echo "--- dunst log"
head -5 /tmp/dunst.log
