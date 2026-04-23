#!/bin/bash
# Build script for Trends — Linux
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Trends Linux Build ==="

# Проверка виртуального окружения
if [ ! -f ".venv/bin/activate" ]; then
    echo "ERROR: .venv not found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

source .venv/bin/activate

# Проверка PyInstaller
if ! python -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip install pyinstaller
fi

# Предупреждение про snap7
if ! python -c "import ctypes; ctypes.CDLL('libsnap7.so')" 2>/dev/null; then
    echo "WARNING: libsnap7.so not found — S7 PLC connection won't work."
    echo "  Install: sudo apt install libsnap7-1"
    echo "  Or download from: https://sourceforge.net/projects/snap7/"
    echo ""
fi

# Предупреждение про AppIndicator (трей GNOME)
if ! python -c "import gi; gi.require_version('AppIndicator3', '0.1'); from gi.repository import AppIndicator3" 2>/dev/null; then
    echo "WARNING: AppIndicator3 not found — tray icon may not work on GNOME."
    echo "  Install: sudo apt install gir1.2-appindicator3-0.1"
    echo "  Also enable extension: https://extensions.gnome.org/extension/615/appindicator-support/"
    echo ""
fi

# Сборка
echo "Building..."
pyinstaller trends_linux.spec --clean

echo ""
echo "=== Build complete ==="
echo "Binary: dist/Trends/Trends"
echo ""
echo "To install desktop launcher:"
echo "  bash install_desktop.sh"
