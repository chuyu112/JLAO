# JLAO - 翡翠直播间实时 AI 优化系统

Jade Live AI Optimizer（JLAO）是一个面向翡翠直播间的实时 AI 场控副驾系统。

当前阶段目标：一个月内完成可演示 MVP Demo。

## 技术栈

```text
前端：Vue 3 + Vite + TypeScript + Pinia + Naive UI
后端：Python + FastAPI + SQLAlchemy + PostgreSQL + WebSocket
视频处理：FFmpeg + OpenCV + Pillow
AI：FunASR + PaddleOCR + 大模型 API
```

## 🚀 快速开始

### 本地开发（GPU 加速）

```bash
# 1. 创建 Conda 环境
conda create -n jlao python=3.11 -y
conda activate jlao

# 2. 安装依赖（GPU 版本）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install funasr paddlepaddle-gpu==2.6.2 paddleocr==2.9.1
pip install -r backend/requirements.txt

# 3. 启动后端
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# 4. 启动前端（另开终端）
cd frontend
npm install
npm run dev
```

### 服务器部署

```bash
# 上传发布包到服务器
scp jlao-release.tar.gz root@47.120.41.143:/tmp/

# 在服务器上执行安装
ssh root@47.120.41.143
bash /tmp/jlao-release/deploy/server-install.sh
```

## 📁 项目结构

```text
JLAO/
├── backend/              # 后端代码
│   ├── app/             # FastAPI 应用
│   ├── requirements.txt # Python 依赖
│   └── .venv/           # 虚拟环境
├── frontend/            # 前端代码
│   └── dist/           # 构建产物
├── deploy/              # 部署脚本
├── Dockerfile           # Docker 配置
├── docker-compose.yml   # Docker Compose 配置
├── docker-run.bat       # Docker 启动脚本
├── setup-env.bat        # 环境配置脚本
├── deploy-server.bat    # 服务器部署脚本
├── SETUP.md             # 换电脑部署指南
└── DOCKER.md            # Docker 部署指南
```

## 🛠️ 技术栈

| 组件 | 技术 |
|---|---|
| 后端 | FastAPI + Python 3.11 |
| 前端 | Vue.js + TypeScript |
| 语音识别 | FunASR (GPU) |
| OCR | PaddleOCR (GPU) |
| 数据库 | PostgreSQL |
| 部署 | Nginx + Systemd |

## 📚 文档

- [换电脑部署指南](SETUP.md) - 新电脑快速部署
- [Docker 部署指南](DOCKER.md) - Docker 方式部署
- [服务器部署](deploy-server.bat) - 服务器部署脚本

## 📝 环境变量

复制 `.env.example` 到 `.env` 并配置：

```env
# GPU 加速
FUNASR_DEVICE=cuda
PADDLEOCR_USE_GPU=true

# 语音/OCR 默认使用本地引擎，不配置付费云服务密钥
STT_PROVIDER=local
LOCAL_STT_ENGINE=funasr
```

## 🆘 常见问题

### 换电脑后如何快速部署？

1. 克隆代码仓库
2. 按照 [SETUP.md](SETUP.md) 安装依赖
3. 复制 `.env` 配置文件
4. 启动服务

### 如何备份模型？

模型缓存目录：
- FunASR: `~/.cache/modelscope/`
- PaddleOCR: `~/.paddleocr/`

复制这些目录到新电脑即可。

## 当前 MVP 闭环

```text
创建直播
-> 选择翡翠商品
-> 模拟直播转写流
-> AI 生成建议
-> 人工审核建议
-> 生成直播复盘
```

## 目录

```text
frontend/   前端中控台
backend/    后端 API、WebSocket、AI 建议服务
data/       Demo 样例数据
docs/       后续可迁移中文文档
```

## 开发启动

前端：

```bash
cd frontend
npm install
npm run dev
```

后端：

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

当前 Windows 环境如果 `python` 是应用商店占位入口，需要先安装 Python 3.11+ 并关闭应用执行别名。

Windows 快速启动：

```powershell
.\scripts\start-backend.ps1
.\scripts\start-frontend.ps1
```

本地截屏助手：

```powershell
.\capture-helper\start-helper.ps1
```

浏览器抽帧黑屏时，启动本地截屏助手，然后在 JLAO 页面点击"本地助手截一次"。自动连续截图暂时关闭，避免误采集。

部署到服务器：

```powershell
.\deploy\deploy.ps1
```

当前默认部署目标：

```text
http://47.120.41.143
```

Demo 登录：

```text
operator / jlao123
anchor / jlao123
admin / jlao123
```
