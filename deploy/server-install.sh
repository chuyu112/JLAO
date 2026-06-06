#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/jlao"
WEB_DIR="/var/www/jlao"
RELEASE_DIR="/tmp/jlao-release"
VENV_DIR="$APP_DIR/.venv"

echo "[JLAO] Installing system dependencies..."
if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y python3 python3-venv python3-pip nginx tar libgl1 libglib2.0-0
  if ! apt-get install -y tesseract-ocr tesseract-ocr-chi-sim; then
    echo "[JLAO] Optional OCR dependency install skipped: tesseract Chinese packages unavailable."
  fi
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y python3.11 python3.11-pip nginx tar mesa-libGL glib2
  if ! dnf install -y tesseract tesseract-langpack-chi_sim; then
    echo "[JLAO] Optional OCR dependency install skipped: tesseract Chinese packages unavailable."
  fi
elif command -v yum >/dev/null 2>&1; then
  yum install -y python3.11 python3.11-pip nginx tar mesa-libGL glib2
  if ! yum install -y tesseract tesseract-langpack-chi_sim; then
    echo "[JLAO] Optional OCR dependency install skipped: tesseract Chinese packages unavailable."
  fi
else
  echo "Unsupported Linux distribution: apt-get/dnf/yum not found" >&2
  exit 1
fi

PYTHON_BIN="$(command -v python3.11 || command -v python3)"
echo "[JLAO] Using Python: $($PYTHON_BIN --version)"

echo "[JLAO] Creating directories..."
mkdir -p "$APP_DIR" "$WEB_DIR"
mkdir -p "$APP_DIR/models"

echo "[JLAO] Installing backend..."
rm -rf "$APP_DIR/backend"
cp -R "$RELEASE_DIR/backend" "$APP_DIR/backend"
mkdir -p "$APP_DIR/data"
rm -rf "$APP_DIR/data/samples"
cp -R "$RELEASE_DIR/data/samples" "$APP_DIR/data/samples"
if [ -d "$RELEASE_DIR/data/jade_yolo" ]; then
  mkdir -p "$APP_DIR/data/jade_yolo/images/train" \
    "$APP_DIR/data/jade_yolo/images/val" \
    "$APP_DIR/data/jade_yolo/images/test" \
    "$APP_DIR/data/jade_yolo/labels/train" \
    "$APP_DIR/data/jade_yolo/labels/val" \
    "$APP_DIR/data/jade_yolo/labels/test"
  if [ -f "$RELEASE_DIR/data/jade_yolo/dataset.yaml" ]; then
    cp "$RELEASE_DIR/data/jade_yolo/dataset.yaml" "$APP_DIR/data/jade_yolo/dataset.yaml"
  fi
  if [ -f "$RELEASE_DIR/data/jade_yolo/README.md" ]; then
    cp "$RELEASE_DIR/data/jade_yolo/README.md" "$APP_DIR/data/jade_yolo/README.md"
  fi
fi
if [ -d "$RELEASE_DIR/scripts" ]; then
  rm -rf "$APP_DIR/scripts"
  cp -R "$RELEASE_DIR/scripts" "$APP_DIR/scripts"
fi
if [ -f "$RELEASE_DIR/models/jade-yolo.pt" ]; then
  cp "$RELEASE_DIR/models/jade-yolo.pt" "$APP_DIR/models/jade-yolo.pt"
  echo "[JLAO] Installed YOLO model: $APP_DIR/models/jade-yolo.pt"
fi

cd "$APP_DIR/backend"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --upgrade pip

echo "[JLAO] Installing Python dependencies (server mode)..."
# 服务器默认只安装基础依赖；大模型运行优先走 HTTP/Ollama，避免在 CPU 服务器上直接跑大 VLM。
"$VENV_DIR/bin/python" -m pip install fastapi uvicorn pydantic sqlalchemy psycopg python-multipart python-dotenv opencv-python-headless pillow numpy httpx websockets pyjwt bcrypt imageio-ffmpeg aliyun-python-sdk-core

if [ "${JLAO_INSTALL_YOLO:-1}" = "1" ]; then
  echo "[JLAO] Installing optional YOLO runtime..."
  "$VENV_DIR/bin/python" -m pip install ultralytics
  echo "[JLAO] Prewarming YOLO base model..."
  (
    cd "$APP_DIR"
    "$VENV_DIR/bin/python" -c "from pathlib import Path; from ultralytics import YOLO; models=Path('models'); models.mkdir(exist_ok=True); dst=models/'yolo11n.pt'; YOLO(str(dst) if dst.exists() else 'yolo11n.pt'); src=Path('yolo11n.pt'); src.replace(dst) if src.exists() and not dst.exists() else None"
  )
else
  echo "[JLAO] Optional YOLO runtime skipped because JLAO_INSTALL_YOLO=0."
fi

if [ "${JLAO_INSTALL_VLM:-0}" = "1" ]; then
  echo "[JLAO] Installing optional local VLM runtime..."
  if [ -n "${JLAO_TORCH_INDEX_URL:-}" ]; then
    "$VENV_DIR/bin/python" -m pip install torch torchvision --index-url "$JLAO_TORCH_INDEX_URL"
  else
    "$VENV_DIR/bin/python" -m pip install torch torchvision
  fi
  "$VENV_DIR/bin/python" -m pip install transformers accelerate sentencepiece protobuf
else
  echo "[JLAO] Optional local VLM runtime skipped. Use JLAO_VLM_HTTP_URL/JLAO_VLM_HTTP_MODEL for HTTP/Ollama VLM, or set JLAO_INSTALL_VLM=1 and JLAO_VLM_MODEL for local transformers VLM."
fi

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
