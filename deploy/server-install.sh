#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/jlao"
WEB_DIR="/var/www/jlao"
RELEASE_DIR="/tmp/jlao-release"

echo "[JLAO] Installing system dependencies..."
if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y python3 python3-venv python3-pip nginx tar
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y python3.11 python3.11-pip nginx tar
elif command -v yum >/dev/null 2>&1; then
  yum install -y python3.11 python3.11-pip nginx tar
else
  echo "Unsupported Linux distribution: apt-get/dnf/yum not found" >&2
  exit 1
fi

PYTHON_BIN="$(command -v python3.11 || command -v python3)"
echo "[JLAO] Using Python: $($PYTHON_BIN --version)"

echo "[JLAO] Creating directories..."
mkdir -p "$APP_DIR" "$WEB_DIR"

echo "[JLAO] Installing backend..."
rm -rf "$APP_DIR/backend"
cp -R "$RELEASE_DIR/backend" "$APP_DIR/backend"
mkdir -p "$APP_DIR/data"
rm -rf "$APP_DIR/data/samples"
cp -R "$RELEASE_DIR/data/samples" "$APP_DIR/data/samples"
cd "$APP_DIR/backend"
"$PYTHON_BIN" -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "[JLAO] Installing frontend..."
rm -rf "$WEB_DIR"/*
cp -R "$RELEASE_DIR/frontend-dist"/* "$WEB_DIR"/

echo "[JLAO] Installing service and nginx config..."
cp "$RELEASE_DIR/deploy/jlao-backend.service" /etc/systemd/system/jlao-backend.service
cp "$RELEASE_DIR/deploy/nginx-jlao.conf" /etc/nginx/conf.d/jlao.conf

if [ -f /etc/nginx/conf.d/default.conf ]; then
  mv /etc/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf.bak.$(date +%Y%m%d%H%M%S)
fi

systemctl daemon-reload
systemctl enable jlao-backend
systemctl restart jlao-backend

nginx -t
systemctl enable nginx
systemctl restart nginx

echo "[JLAO] Deployed successfully."
echo "[JLAO] Backend health: http://127.0.0.1:8001/health"
