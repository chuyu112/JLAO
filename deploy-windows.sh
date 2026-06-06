#!/usr/bin/env bash
# JLAO 部署脚本 - Windows Git Bash 版本
# 用法: ./deploy-windows.sh

set -euo pipefail

SERVER="root@47.120.41.143"
SERVER_IP="47.120.41.143"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PACKAGE="$ROOT_DIR/jlao-release.tar.gz"
TEMP_DIR="$ROOT_DIR/.release"

echo "========================================"
echo "  JLAO 部署脚本"
echo "========================================"
echo ""
echo "项目目录: $ROOT_DIR"
echo ""

# 检查必要的命令
for cmd in tar; do
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
echo ""
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

echo ""
echo "[JLAO] 发布包已创建: $PACKAGE"
echo ""
echo "========================================"
echo "  发布包准备完成！"
echo "========================================"
echo ""
echo "请手动执行以下步骤完成部署："
echo ""
echo "1. 上传发布包到服务器："
echo "   scp $PACKAGE root@$SERVER_IP:/tmp/jlao-release.tar.gz"
echo ""
echo "2. SSH 登录服务器："
echo "   ssh root@$SERVER_IP"
echo ""
echo "3. 在服务器上执行安装："
echo "   rm -rf /tmp/jlao-release && mkdir -p /tmp/jlao-release"
echo "   tar -xzf /tmp/jlao-release.tar.gz -C /tmp/jlao-release"
echo "   bash /tmp/jlao-release/deploy/server-install.sh"
echo ""
echo "========================================"
