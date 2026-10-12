#!/bin/bash
# Starts: demo usage API, VNC desktop (XFCE) as user "demo", noVNC on :6080.
set -e
APP_TAR=$(ls /pkg/claude-usage-tray-*-linux-*.tar.gz | head -1)
mkdir -p /opt/cut && tar -xzf "$APP_TAR" -C /opt/cut
APP_DIR=$(ls -d /opt/cut/*/claude-usage-tray)
python3 /opt/desktop/fake_api.py &

HOME_DIR=/home/demo
mkdir -p $HOME_DIR/.claude $HOME_DIR/.config/autostart $HOME_DIR/.vnc
cat > $HOME_DIR/.claude/.credentials.json <<JSON
{"claudeAiOauth": {"accessToken": "demo-token", "expiresAt": $(( ($(date +%s) + 604800) * 1000 )),
 "subscriptionType": "max", "rateLimitTier": "default_claude_max_5x"}}
JSON
cat > $HOME_DIR/.config/autostart/cut-demo.desktop <<DESK
[Desktop Entry]
Type=Application
Name=Claude Usage Tray (demo)
Exec=env CLAUDE_USAGE_TEST_API=http://127.0.0.1:18765 $APP_DIR/claude-usage-tray
X-GNOME-Autostart-Delay=3
DESK
# panel launcher + desktop shortcut for restarting the app
mkdir -p $HOME_DIR/Desktop
cat > $HOME_DIR/Desktop/claude-usage-tray.desktop <<DESK
[Desktop Entry]
Type=Application
Name=Claude Usage Tray
Exec=env CLAUDE_USAGE_TEST_API=http://127.0.0.1:18765 $APP_DIR/claude-usage-tray
Icon=/opt/cut/$(basename $(dirname $APP_DIR))/icons/claude-usage-tray-128.png
Terminal=false
DESK
chmod +x $HOME_DIR/Desktop/*.desktop
cat > $HOME_DIR/.vnc/xstartup <<'XS'
#!/bin/bash
export LANG=hu_HU.UTF-8 LC_ALL=hu_HU.UTF-8
exec dbus-launch --exit-with-session startxfce4
XS
chmod +x $HOME_DIR/.vnc/xstartup
chown -R demo:demo $HOME_DIR

su demo -c "vncserver :1 -geometry 1366x768 -depth 24 -SecurityTypes None -localhost yes -xstartup /home/demo/.vnc/xstartup" 
exec websockify --web /usr/share/novnc 6080 localhost:5901
