#!/bin/bash
# Устанавливает systemd user service для автозапуска Trends
set -e

INSTALL_DIR="$HOME/.local/lib/trends"
SERVICE_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SERVICE_DIR/trends.service"

if [ ! -f "$INSTALL_DIR/Trends" ]; then
    echo "ERROR: Binary not found. Run install_desktop.sh first."
    exit 1
fi

mkdir -p "$SERVICE_DIR"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Trends PLC Data Collector
After=network.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/Trends
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/%U/bus

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable trends.service
systemctl --user start trends.service

echo "=== Autostart enabled ==="
echo "Status: systemctl --user status trends"
echo "Logs:   journalctl --user -u trends -f"
echo "Stop:   systemctl --user stop trends"
echo "Disable autostart: systemctl --user disable trends"
