#!/bin/sh
# Per-user installation of the portable build: no root needed. Usage: ./install.sh [--uninstall]
set -e
NAME=claude-usage-tray
HERE="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${XDG_DATA_HOME:-$HOME/.local/share}"
OPT="$HOME/.local/opt/$NAME"
BIN="$HOME/.local/bin"

if [ "$1" = "--uninstall" ]; then
    rm -rf "$OPT" "$BIN/$NAME" "$PREFIX/applications/$NAME.desktop"
    rm -f "$PREFIX"/icons/hicolor/*/apps/$NAME.png
    rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/ClaudeUsageTray.desktop"
    echo "Claude Usage Tray removed (settings in ${XDG_CONFIG_HOME:-$HOME/.config}/ClaudeUsageTray were kept)."
    exit 0
fi

mkdir -p "$OPT" "$BIN" "$PREFIX/applications"
rm -rf "$OPT"/*
cp -a "$HERE/$NAME/." "$OPT/"
ln -sf "$OPT/$NAME" "$BIN/$NAME"
for icon in "$HERE"/icons/*.png; do
    size="$(basename "$icon" .png | sed 's/.*-//')"
    mkdir -p "$PREFIX/icons/hicolor/${size}x${size}/apps"
    cp "$icon" "$PREFIX/icons/hicolor/${size}x${size}/apps/$NAME.png"
done
sed "s|^Exec=.*|Exec=$OPT/$NAME|" "$HERE/$NAME.desktop" > "$PREFIX/applications/$NAME.desktop"
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$PREFIX/applications" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t "$PREFIX/icons/hicolor" || true
echo "Claude Usage Tray installed to $OPT"
echo "Start it from the application menu or run: $BIN/$NAME"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "Note: $BIN is not in your PATH.";; esac
