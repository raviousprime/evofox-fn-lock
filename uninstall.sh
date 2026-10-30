#!/usr/bin/env bash
set -euo pipefail

# EvoFox Fn Lock Uninstaller for Ubuntu 24.04+
echo "==> Uninstalling EvoFox Fn Lock Daemon..."

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root (or with sudo)."
    exit 1
fi

SERVICE_FILE="/etc/systemd/system/evofox-fn-lock.service"
INSTALL_DIR="/opt/evofox-fn-lock"
CLI_BIN="/usr/local/bin/evofox-fn-lock"

if systemctl is-active --quiet evofox-fn-lock.service 2>/dev/null; then
    echo "--> Stopping evofox-fn-lock service..."
    systemctl stop evofox-fn-lock.service
fi

if systemctl is-enabled --quiet evofox-fn-lock.service 2>/dev/null; then
    echo "--> Disabling evofox-fn-lock service..."
    systemctl disable evofox-fn-lock.service
fi

if [[ -f "$SERVICE_FILE" ]]; then
    echo "--> Removing systemd service unit..."
    rm -f "$SERVICE_FILE"
    systemctl daemon-reload
fi

if [[ -f "$CLI_BIN" ]]; then
    echo "--> Removing CLI binary..."
    rm -f "$CLI_BIN"
fi

if [[ -d "$INSTALL_DIR" ]]; then
    echo "--> Removing installation directory $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
fi

echo "==> Daemon removed and physical keyboard ungrabbed."
echo "Note: Configuration (/etc/evofox-fn-lock) and state (/var/lib/evofox-fn-lock) have been retained."
echo "To remove them as well, run: rm -rf /etc/evofox-fn-lock /var/lib/evofox-fn-lock"

