#!/bin/bash
# Устанавливает Trends в ~/.local и добавляет в launcher GNOME
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$SCRIPT_DIR/dist/Trends"

if [ ! -f "$DIST_DIR/Trends" ]; then
    echo "ERROR: Binary not found. Run build.sh first."
    exit 1
fi

INSTALL_DIR="$HOME/.local/lib/trends"
BIN_LINK="$HOME/.local/bin/trends"
DESKTOP_FILE="$HOME/.local/share/applications/trends.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"

echo "Installing to $INSTALL_DIR ..."

# Копируем бинарники
mkdir -p "$INSTALL_DIR"
cp -r "$DIST_DIR"/. "$INSTALL_DIR/"

# Иконка
mkdir -p "$ICON_DIR"
cp "$SCRIPT_DIR/assets/trends.png" "$ICON_DIR/trends.png"

# Симлинк в PATH
mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_DIR/Trends" "$BIN_LINK"

# .desktop файл
mkdir -p "$(dirname "$DESKTOP_FILE")"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Trends
Comment=PLC Data Collection and Visualization
Exec=$INSTALL_DIR/Trends
Icon=trends
Terminal=false
Categories=Utility;Science;
StartupNotify=false
EOF

# Обновляем кэш иконок
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo ""
echo "=== Installed ==="
echo "Launch from terminal: trends"
echo "Or find 'Trends' in GNOME app launcher"
echo ""
echo "To add to autostart (systemd user service):"
echo "  bash install_autostart.sh"
