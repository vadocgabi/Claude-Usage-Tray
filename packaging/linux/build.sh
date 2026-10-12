#!/bin/bash
# Builds the Linux packages inside a Debian 11 container (glibc 2.31 => runs on every current distribution).
#   docker build -t cut-build -f packaging/linux/Dockerfile.build .
#   docker run --rm -v "$PWD":/src -v "$PWD/dist-linux":/out cut-build
set -euo pipefail
NAME=claude-usage-tray
cd /src
VERSION="$(python -c 'import claude_usage; print(claude_usage.__version__)')"
ARCH_DEB="$(dpkg --print-architecture)"
ARCH_TAR="$(uname -m)"
WORK=/tmp/cut-build
rm -rf "$WORK" && mkdir -p "$WORK" /out

# Text files that end up in the packages must have LF endings (a Windows checkout may have converted them).
sed -i 's/\r$//' packaging/linux/install.sh packaging/linux/claude-usage-tray.desktop

echo "== PyInstaller"
pip install --no-cache-dir -q pillow pystray python-xlib jeepney keyring curl_cffi pyinstaller
pyinstaller --noconfirm --clean --onedir --name "$NAME" \
    --distpath "$WORK/dist" --workpath "$WORK/build" --specpath "$WORK" \
    --collect-all curl_cffi --collect-all keyring --collect-all jeepney --collect-submodules secretstorage \
    --copy-metadata keyring --hidden-import pystray._xorg --collect-submodules Xlib \
    --exclude-module matplotlib --exclude-module numpy \
    claude_usage_tray.py
BUNDLE="$WORK/dist/$NAME"
cp LICENSE "$BUNDLE/" 2>/dev/null || true
"$BUNDLE/$NAME" --version

echo "== tar.gz (portable + per-user installer)"
TAR_DIR="$WORK/tar/$NAME-$VERSION"
mkdir -p "$TAR_DIR/icons"
cp -a "$BUNDLE" "$TAR_DIR/$NAME"
cp packaging/linux/icons/*.png "$TAR_DIR/icons/"
cp packaging/linux/install.sh packaging/linux/claude-usage-tray.desktop LICENSE "$TAR_DIR/"
tar -C "$WORK/tar" -czf "/out/$NAME-$VERSION-linux-$ARCH_TAR.tar.gz" "$NAME-$VERSION"

echo "== deb"
PKG="$WORK/deb"
mkdir -p "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" "$PKG/usr/share/applications" "$PKG/usr/share/doc/$NAME"
cp -a "$BUNDLE" "$PKG/opt/$NAME"
ln -s "../../opt/$NAME/$NAME" "$PKG/usr/bin/$NAME"
cp packaging/linux/claude-usage-tray.desktop "$PKG/usr/share/applications/"
for icon in packaging/linux/icons/*.png; do
    size="$(basename "$icon" .png | sed 's/.*-//')"
    install -D -m 644 "$icon" "$PKG/usr/share/icons/hicolor/${size}x${size}/apps/$NAME.png"
done
cp LICENSE "$PKG/usr/share/doc/$NAME/copyright"
INSTALLED_KB="$(du -sk "$PKG" | cut -f1)"
cat > "$PKG/DEBIAN/control" <<CONTROL
Package: $NAME
Version: $VERSION
Section: utils
Priority: optional
Architecture: $ARCH_DEB
Installed-Size: $INSTALLED_KB
Depends: libc6 (>= 2.31), libx11-6, libxext6, libxft2, libfontconfig1, libfreetype6
Recommends: libnotify-bin
Suggests: gnome-shell-extension-appindicator, gnome-keyring
Maintainer: Vadóc Gábor <vadocgabi@gmail.com>
Homepage: https://github.com/vadocgabi/Claude-Usage-Tray
Description: Claude usage monitor for the system tray
 Shows the claude.ai session and weekly usage limits in the system tray, with
 per-model limits, pace and forecast, desktop notifications and local token
 statistics. Unofficial; not affiliated with Anthropic.
CONTROL
dpkg-deb --build --root-owner-group "$PKG" "/out/${NAME}_${VERSION}_${ARCH_DEB}.deb" >/dev/null

echo "== AppImage"
APPDIR="$WORK/AppDir"
mkdir -p "$APPDIR"
cp -a "$BUNDLE" "$APPDIR/$NAME"
cp packaging/linux/claude-usage-tray.desktop "$APPDIR/"
cp packaging/linux/icons/claude-usage-tray-256.png "$APPDIR/$NAME.png"
cp packaging/linux/icons/claude-usage-tray-256.png "$APPDIR/.DirIcon"
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/claude-usage-tray/claude-usage-tray" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"
TOOL="$WORK/appimagetool"
curl -fsSL -o "$TOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH_TAR.AppImage"
chmod +x "$TOOL"
ARCH="$ARCH_TAR" "$TOOL" --appimage-extract-and-run --no-appstream "$APPDIR" "/out/ClaudeUsageTray-$VERSION-$ARCH_TAR.AppImage" >/dev/null 2>&1

ls -la /out
