#!/bin/bash
# Smoke test of the packaged binary on a bare distribution image.
# Mounts: /pkg = dist-linux (read-only). Prints one line per check, exits non-zero on failure.
set -u
FAIL=0
ok()   { echo "  [PASS] $1"; }
bad()  { echo "  [FAIL] $1"; FAIL=1; }
. /etc/os-release
echo "== $PRETTY_NAME  (glibc $(ldd --version | head -1 | awk '{print $NF}'))"

# --- minimal desktop runtime: an X server plus the X libraries every desktop already has
if command -v apt-get >/dev/null; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null 2>&1
    apt-get install -y -qq --no-install-recommends xvfb xauth libx11-6 libxext6 libxft2 libfontconfig1 fonts-dejavu-core \
        ca-certificates >/dev/null 2>&1
elif command -v dnf >/dev/null; then
    dnf install -y -q xorg-x11-server-Xvfb xauth libX11 libXext libXft fontconfig dejavu-sans-fonts >/dev/null 2>&1
elif command -v pacman >/dev/null; then
    pacman -Sy --noconfirm --quiet xorg-server-xvfb xorg-xauth libx11 libxext libxft fontconfig ttf-dejavu >/dev/null 2>&1
fi
command -v Xvfb >/dev/null && ok "X server available" || bad "X server missing"

# --- portable tar.gz
mkdir -p /opt/t && tar -xzf /pkg/claude-usage-tray-*-linux-x86_64.tar.gz -C /opt/t
BIN=$(ls -d /opt/t/*/claude-usage-tray/claude-usage-tray)
VERSION_OUT=$("$BIN" --version 2>&1)
echo "$VERSION_OUT" | grep -q "Claude Usage Tray" && ok "binary starts: $VERSION_OUT" || bad "binary does not start: $VERSION_OUT"

export HOME=/tmp/home XDG_CONFIG_HOME=/tmp/home/.config
mkdir -p "$HOME"
Xvfb :99 -screen 0 1024x768x24 >/dev/null 2>&1 &
sleep 1
export DISPLAY=:99
REPORT=$("$BIN" --diagnose 2>&1); CODE=$?
echo "$REPORT" | sed 's/^/      /'
[ $CODE -eq 0 ] && ok "diagnose: essentials work (Tk window, icon rendering, config folder)" || bad "diagnose reported a failure"
echo "$REPORT" | grep -q "cookie mode (curl_cffi)  curl_cffi" && ok "cookie mode library bundled" || bad "curl_cffi missing"

# --- per-user installer of the tarball
INSTALL_DIR=$(dirname "$(dirname "$BIN")")
sh "$INSTALL_DIR/install.sh" >/dev/null 2>&1
[ -x "$HOME/.local/bin/claude-usage-tray" ] && [ -f "$HOME/.local/share/applications/claude-usage-tray.desktop" ] \
    && ok "install.sh installs the binary and the desktop entry" || bad "install.sh failed"
"$HOME/.local/bin/claude-usage-tray" --version >/dev/null 2>&1 && ok "installed launcher works" || bad "installed launcher broken"
sh "$INSTALL_DIR/install.sh" --uninstall >/dev/null 2>&1
[ ! -e "$HOME/.local/bin/claude-usage-tray" ] && ok "uninstall removes it again" || bad "uninstall left files"

# --- .deb on Debian-family systems
if command -v apt-get >/dev/null; then
    apt-get install -y -qq /pkg/claude-usage-tray_*_amd64.deb >/dev/null 2>&1 && ok ".deb installs (dependencies resolved)" || bad ".deb install failed"
    command -v claude-usage-tray >/dev/null && claude-usage-tray --version >/dev/null 2>&1 \
        && ok "installed command works" || bad "installed command missing"
    [ -f /usr/share/applications/claude-usage-tray.desktop ] && [ -f /usr/share/icons/hicolor/256x256/apps/claude-usage-tray.png ] \
        && ok "desktop entry and icons installed" || bad "desktop files missing"
    apt-get remove -y -qq claude-usage-tray >/dev/null 2>&1
    [ ! -e /usr/bin/claude-usage-tray ] && ok ".deb removes cleanly" || bad ".deb removal left files"
fi

# --- AppImage (no FUSE in containers: extract-and-run)
IMG=$(ls /pkg/*.AppImage)
APPIMAGE_EXTRACT_AND_RUN=1 "$IMG" --version 2>&1 | grep -q "Claude Usage Tray" && ok "AppImage runs" || bad "AppImage does not run"

echo "== result: $([ $FAIL -eq 0 ] && echo OK || echo FAILED)"
exit $FAIL
