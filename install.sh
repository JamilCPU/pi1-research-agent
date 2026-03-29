#!/bin/bash
# Pi 1 Research Agent — installation script
# Run as root or with sudo on Raspberry Pi 1 (ARM64, Raspberry Pi OS)

set -euo pipefail

INSTALL_DIR="/opt/pi1-research-agent"
SERVICE_FILE="/etc/systemd/system/pi1-research-agent.service"
ENV_FILE="/etc/pi1-research-agent.env"
LOG_DIR="/var/log/pi1-research-agent"

echo "==> Installing Pi 1 Research Agent..."

# ── System dependencies ────────────────────────────────────────────────────
echo "==> Installing system packages..."
apt-get update -qq
apt-get install -y python3 python3-pip python3-venv git

# ── Create install directory ───────────────────────────────────────────────
echo "==> Setting up $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp -r ./* "$INSTALL_DIR/"
chown -R pi:pi "$INSTALL_DIR"

# ── Python virtual environment ─────────────────────────────────────────────
echo "==> Creating Python virtual environment..."
sudo -u pi python3 -m venv "$INSTALL_DIR/venv"
sudo -u pi "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
sudo -u pi "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# ── Log directory ──────────────────────────────────────────────────────────
echo "==> Creating log directory..."
mkdir -p "$LOG_DIR"
chown -R pi:pi "$LOG_DIR"

# ── Environment file ───────────────────────────────────────────────────────
if [ ! -f "$ENV_FILE" ]; then
    echo "==> Creating environment file at $ENV_FILE..."
    cat > "$ENV_FILE" << 'EOF'
# Pi 1 Research Agent — environment variables
# Set your Anthropic API key here:
ANTHROPIC_API_KEY=your_anthropic_api_key_here
EOF
    chmod 600 "$ENV_FILE"
    echo "  ** Edit $ENV_FILE and set your ANTHROPIC_API_KEY before starting the service **"
else
    echo "==> $ENV_FILE already exists — skipping"
fi

# ── Systemd service ────────────────────────────────────────────────────────
echo "==> Installing systemd service..."
cp "$INSTALL_DIR/systemd/pi1-research-agent.service" "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable pi1-research-agent

echo ""
echo "==> Installation complete."
echo ""
echo "Next steps:"
echo "  1. Edit $ENV_FILE and set ANTHROPIC_API_KEY"
echo "  2. Edit $INSTALL_DIR/config.yaml if needed"
echo "     (cycle interval, thresholds, Ollama model, handoff folder path)"
echo "  3. Ensure the handoff folder exists and is writable:"
echo "       mkdir -p /shared/handoff && chown pi:pi /shared/handoff"
echo "  4. Start the agent:"
echo "       systemctl start pi1-research-agent"
echo "  5. Check status:"
echo "       systemctl status pi1-research-agent"
echo "       journalctl -u pi1-research-agent -f"
