#!/usr/bin/env bash
set -euo pipefail

# JLAO 部署脚本 - 支持密码连接
# 用法: ./deploy-with-password.sh <密码>

SERVER="root@47.120.41.143"
SERVER_IP="47.120.41.143"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PACKAGE="$ROOT_DIR/jlao-release.tar.gz"
TEMP_DIR="$ROOT_DIR/.release"

echo "[JLAO] 开始部署..."
echo "[JLAO] 项目目录: $ROOT_DIR"

# 检查参数
if [ $# -lt 1 ]; then
    echo "用法: $0 <服务器密码>"
    echo "示例: $0 your_password"
    exit 1
fi

PASSWORD="$1"

# 检查必要的命令
for cmd in ssh scp tar; do
    if ! command -v $cmd &> /dev/null; then
        echo "错误: 缺少命令 $cmd"
        exit 1
    fi
done

# 构建前端
echo "[JLAO] 构建前端..."
cd "$ROOT_DIR/frontend"
if [ -f package.json ]; then
    export VITE_API_BASE="https://jlao.szkakayiduo.com"
    npm run build
else
    echo "警告: 前端 package.json 不存在，跳过前端构建"
fi

# 准备发布包
echo "[JLAO] 准备发布包..."
rm -rf "$TEMP_DIR"
mkdir -p "$TEMP_DIR/frontend-dist"
mkdir -p "$TEMP_DIR/backend"
mkdir -p "$TEMP_DIR/data"
mkdir -p "$TEMP_DIR/deploy"

# 复制后端代码
cp -r "$ROOT_DIR/backend/app" "$TEMP_DIR/backend/"
cp "$ROOT_DIR/backend/requirements.txt" "$TEMP_DIR/backend/"

# 复制数据样本
if [ -d "$ROOT_DIR/data/samples" ]; then
    cp -r "$ROOT_DIR/data/samples" "$TEMP_DIR/data/"
fi

# 复制前端构建产物
if [ -d "$ROOT_DIR/frontend/dist" ]; then
    cp -r "$ROOT_DIR/frontend/dist/"* "$TEMP_DIR/frontend-dist/"
fi

# 复制部署脚本
cp -r "$ROOT_DIR/deploy/"* "$TEMP_DIR/deploy/"

# 打包
cd "$TEMP_DIR"
tar -czf "$PACKAGE" .

echo "[JLAO] 发布包已创建: $PACKAGE"

# 上传到服务器
echo "[JLAO] 上传到服务器..."
# 使用 sshpass 或 expect 来自动输入密码
if command -v sshpass &> /dev/null; then
    sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=accept-new "$PACKAGE" "$SERVER:/tmp/jlao-release.tar.gz"
else
    # 使用 expect 脚本
    cat > /tmp/scp-expect.sh << 'EOF'
#!/usr/bin/env expect -f
set password [lindex $argv 0]
set src [lindex $argv 1]
set dst [lindex $argv 2]
spawn scp -o StrictHostKeyChecking=accept-new "$src" "$dst"
expect "password:"
send "$password\r"
expect eof
EOF
    chmod +x /tmp/scp-expect.sh
    if command -v expect &> /dev/null; then
        expect /tmp/scp-expect.sh "$PASSWORD" "$PACKAGE" "$SERVER:/tmp/jlao-release.tar.gz"
    else
        echo "错误: 需要安装 sshpass 或 expect 来自动输入密码"
        echo "请安装其中之一:"
        echo "  - Windows: choco install sshpass"
        echo "  - Ubuntu/Debian: sudo apt-get install sshpass"
        echo "  - CentOS/RHEL: sudo yum install sshpass"
        exit 1
    fi
fi

echo "[JLAO] 在服务器上安装..."
# 创建远程安装脚本
cat > /tmp/remote-install.sh << 'EOF'
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
  dnf install -y python3 python3-pip nginx tar
elif command -v yum >/dev/null 2>&1; then
  yum install -y python3 python3-pip nginx tar
else
  echo "Unsupported Linux distribution" >&2
  exit 1
fi

PYTHON_BIN="$(command -v python3)"
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

# 安装依赖（CPU 版本，服务器通常没有 GPU）
echo "[JLAO] Installing Python dependencies..."
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
EOF

# 上传并执行远程安装脚本
if command -v sshpass &> /dev/null; then
    sshpass -p "$PASSWORD" scp -o StrictHostKeyChecking=accept-new /tmp/remote-install.sh "$SERVER:/tmp/remote-install.sh"
    sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=accept-new "$SERVER" "rm -rf /tmp/jlao-release && mkdir -p /tmp/jlao-release && tar -xzf /tmp/jlao-release.tar.gz -C /tmp/jlao-release && bash /tmp/remote-install.sh"
else
    # 使用 expect
    cat > /tmp/ssh-expect.sh << 'EOF'
#!/usr/bin/env expect -f
set password [lindex $argv 0]
set cmd [lindex $argv 1]
spawn ssh -o StrictHostKeyChecking=accept-new root@47.120.41.143 "$cmd"
expect "password:"
send "$password\r"
expect eof
EOF
    chmod +x /tmp/ssh-expect.sh

    expect /tmp/ssh-expect.sh "$PASSWORD" "rm -rf /tmp/jlao-release && mkdir -p /tmp/jlao-release && tar -xzf /tmp/jlao-release.tar.gz -C /tmp/jlao-release && bash /tmp/remote-install.sh"
fi

echo "[JLAO] 部署完成: https://jlao.szkakayiduo.com"
