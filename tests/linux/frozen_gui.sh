#!/bin/bash
# Runs the full GUI scenarios against the packaged (PyInstaller) binary instead of the source tree.
set -u
mkdir -p /opt/t && tar -xzf /pkg/claude-usage-tray-*-linux-*.tar.gz -C /opt/t
export APP_CMD="$(ls -d /opt/t/*/claude-usage-tray/claude-usage-tray)"
STATUS=0
for scenario in "$@"; do
    python3 /src/tests/linux/gui_test.py "$scenario" /out || STATUS=1
done
exit $STATUS
