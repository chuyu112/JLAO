# JLAO - 翡翠直播间实时 AI 优化系统

Jade Live AI Optimizer（JLAO）是一个面向翡翠直播间的实时 AI 场控副驾系统。

当前阶段目标：一个月内完成可演示 MVP Demo。

## 技术栈

```text
前端：Vue 3 + Vite + TypeScript + Pinia + Naive UI
后端：Python + FastAPI + SQLAlchemy + PostgreSQL + WebSocket
视频处理：FFmpeg + OpenCV + Pillow
AI：大模型 API + 中文角色提示词
```

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

浏览器抽帧黑屏时，启动本地截屏助手，然后在 JLAO 页面点击“本地助手截一次”。自动连续截图暂时关闭，避免误采集。

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
