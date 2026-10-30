#!/usr/bin/env bash
set -euo pipefail

# EvoFox Fn Lock Installer for Ubuntu 24.04+
echo "==> Installing EvoFox Fn Lock Daemon..."

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root (or with sudo)."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/evofox-fn-lock"
CONFIG_DIR="/etc/evofox-fn-lock"
STATE_DIR="/var/lib/evofox-fn-lock"
SERVICE_FILE="/etc/systemd/system/evofox-fn-lock.service"

# Ensure uinput kernel module is loaded
echo "--> Ensuring uinput module is active..."
modprobe uinput || true
echo "uinput" > /etc/modules-load.d/uinput.conf

# Install required system packages
echo "--> Checking system dependencies..."
if ! command -v python3 &>/dev/null; then
    apt-get update && apt-get install -y python3
fi

# Ensure python3-venv or python3-pip is available
if ! python3 -m venv --help &>/dev/null; then
    apt-get update && apt-get install -y python3-venv
fi

# Create target directories
echo "--> Setting up destination directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$STATE_DIR"

# Copy source code
cp -r "$SCRIPT_DIR/src" "$INSTALL_DIR/"

# Setup Python virtualenv for the daemon
echo "--> Setting up Python environment..."
if [[ ! -d "$INSTALL_DIR/venv" ]]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet
"$INSTALL_DIR/venv/bin/pip" install evdev --quiet

# Copy configuration (preserve existing config if present)
if [[ ! -f "$CONFIG_DIR/config.toml" ]]; then
    echo "--> Installing default config.toml to $CONFIG_DIR..."
    cp "$SCRIPT_DIR/config/config.toml" "$CONFIG_DIR/config.toml"
else
    echo "--> Preserving existing config at $CONFIG_DIR/config.toml"
fi

# Copy systemd service
echo "--> Installing systemd service..."
cp "$SCRIPT_DIR/systemd/evofox-fn-lock.service" "$SERVICE_FILE"

# Create helper CLI tool in /usr/local/bin
echo "--> Creating CLI helper at /usr/local/bin/evofox-fn-lock..."
cat << 'EOF' > /usr/local/bin/evofox-fn-lock
#!/usr/bin/env bash
exec /opt/evofox-fn-lock/venv/bin/python /opt/evofox-fn-lock/src/daemon.py "$@"
EOF
chmod +x /usr/local/bin/evofox-fn-lock

# Reload systemd and start service
echo "--> Enabling and starting evofox-fn-lock service..."
systemctl daemon-reload
systemctl enable evofox-fn-lock.service
systemctl restart evofox-fn-lock.service

echo "==> Installation complete!"
echo "Service status:"
systemctl status evofox-fn-lock.service --no-pager || true
echo ""
echo "Controls:"
echo "  - Check status: evofox-fn-lock --status"
echo "  - Toggle mode:  evofox-fn-lock --toggle (or press Ctrl + Alt + F12)"

