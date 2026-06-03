#!/usr/bin/env bash
# Bootstrap S.E.E.R. on Ubuntu 22.04/24.04 EC2 (t3.small recommended).
# Run as root or with sudo after cloning the repo to /opt/seer.
#
#   sudo bash deploy/ec2/bootstrap.sh
#
# Before running:
#   1. Copy repo to /opt/seer (git clone or rsync)
#   2. Create /opt/seer/bot/.env from .env.example (all secrets)

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/seer}"
BOT_DIR="$REPO_ROOT/bot"
SEER_USER="${SEER_USER:-seer}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo bash $0"
  exit 1
fi

if [[ ! -f "$BOT_DIR/requirements.txt" ]]; then
  echo "Expected $BOT_DIR/requirements.txt — clone repo to $REPO_ROOT first."
  exit 1
fi

echo "==> Installing system packages"
apt-get update -qq
apt-get install -y -qq git python3.12 python3.12-venv python3-pip curl

if ! id "$SEER_USER" &>/dev/null; then
  useradd --system --home "$REPO_ROOT" --shell /usr/sbin/nologin "$SEER_USER"
fi

chown -R "$SEER_USER:$SEER_USER" "$REPO_ROOT"

echo "==> Python venv + dependencies"
sudo -u "$SEER_USER" bash -c "
  cd '$BOT_DIR'
  python3.12 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
"

if [[ ! -f "$BOT_DIR/.env" ]]; then
  echo ""
  echo "WARNING: $BOT_DIR/.env missing."
  echo "  cp $REPO_ROOT/.env.example $BOT_DIR/.env"
  echo "  nano $BOT_DIR/.env   # fill DISCORD_BOT_TOKEN, OPENAI_API_KEY, SUPABASE_*, etc."
  echo ""
fi

echo "==> Installing systemd units"
install -m 644 "$REPO_ROOT/deploy/ec2/seer-discord-bot.service" /etc/systemd/system/
install -m 644 "$REPO_ROOT/deploy/ec2/seer-api.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable seer-discord-bot.service

echo ""
echo "Done. Next:"
echo "  1. Edit $BOT_DIR/.env"
echo "  2. sudo systemctl start seer-discord-bot"
echo "  3. sudo journalctl -u seer-discord-bot -f"
echo ""
echo "Optional API (web UI): open port 8000 in security group, then:"
echo "  sudo systemctl enable --now seer-api"
echo "  curl http://127.0.0.1:8000/health"
