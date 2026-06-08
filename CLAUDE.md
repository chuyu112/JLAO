# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# JLAO 项目上下文

- 服务器地址：47.120.41.143
- 默认部署访问地址：https://jlao.szkakayiduo.com
- 前端部署目录：/var/www/jlao
- 后端端口：8001（服务器）/ 8000（本地）
- 部署流程：见 DEPLOY.md

## 开发命令

**前端（Vue3 + Vite + TypeScript）**

```powershell
cd frontend
npm install
npm run dev        # 开发服务器，端口 5173，--host 0.0.0.0
npm run build      # 生产构建（输出到 frontend/dist）
npm run preview    # 预览生产构建
```

**后端（FastAPI + Python 3.11）**

```powershell
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Windows 快捷启动脚本（项目根目录）：

```powershell
.\scripts\start-backend.ps1   # 优先使用 .venv，回退 .venv-local，再回退系统 Python
.\scripts\start-frontend.ps1  # npm run dev -- --host 127.0.0.1
```

**部署**

```powershell
.\deploy\deploy.ps1           # 构建前端 → 打包 → scp 上传 → 服务器执行 server-install.sh
```

前端手动部署（见 DEPLOY.md）：

```powershell
cd frontend; npm run build
scp -r frontend\dist\* root@47.120.41.143:/var/www/jlao/
ssh root@47.120.41.143 "nginx -t && systemctl restart nginx"
```

## 技术架构

本地算力为主，边缘端+云端混合：

- USB 投屏（scrcpy / QtScrcpy）→ 本地
- 语音实时转换（FunASR）→ 本地 GPU
- 图像 AI（YOLO + VLM + OpenCV）→ 本地 GPU
- 弹幕 OCR（PaddleOCR / RapidOCR）→ 本地 GPU
- 后端（FastAPI）→ 本地运行
- 前端（Vue3 + Vite）→ 服务器 Nginx
- 数据库（PostgreSQL）→ 服务器

数据流：前端（服务器）→ 本地后端（HTTPS）→ 服务器数据库

### 后端架构

**FastAPI 应用入口**：`backend/app/main.py`

路由分层：
- `app/api/` — REST API 路由（按领域分文件：auth.py, sessions.py, products.py, frames.py, suggestions.py, jade_yolo_live.py, scrcpy.py, phone_capture.py, native_stt.py 等）
- `app/ws/` — WebSocket 路由（session_ws.py, stt_ws.py, scrcpy_ws.py）
- `app/services/` — 业务逻辑层（多模态融合、YOLO、VLM、OCR、STT、回放等）
- `app/db.py` — SQLAlchemy 数据库配置，支持 SQLite（默认）和 PostgreSQL 自动切换
- `app/state.py` — 全局内存状态 `AppState`，启动时从数据库 hydrate
- `app/schemas.py` — Pydantic 模型（Product, LiveSession, FrameSnapshot, Suggestion 等）

**数据库**：默认使用 SQLite（`data/jlao-mvp.sqlite`），通过 `DATABASE_URL` 环境变量可切换 PostgreSQL。`db.py` 包含轻量级迁移逻辑（运行时检查表结构并 ALTER ADD COLUMN）。

**认证**：JWT + bcrypt 哈希密码。默认账号：`operator/jlao123`、`anchor/jlao123`、`admin/jlao123`。

### 前端架构

**页面路由**（`frontend/src/router.ts`）：
- `/live` → LiveDashboard（自有运营主控台，YOLO 视频流 + 运营数据墙）
- `/observe` → ObservationDashboard（其它分析，客户线索、成交卡片、复盘骨架）
- `/jade-recognition` → JadeRecognitionLab
- `/products` → ProductLibrary
- `/replay` → ReplayReport
- `/login` → LoginPage

**状态管理**：`frontend/src/stores/jlao.ts`（Pinia）集中管理 WebSocket 连接、session 数据、帧、建议、客户事件等。`frontend/src/stores/auth.ts` 管理登录态。

**API 客户端**（`frontend/src/api/client.ts`）：axios 实例，API_BASE 解析优先级：
1. URL 参数 `?api=xxx`
2. localStorage 保存的 `jlao-api-base`
3. 生产环境（`jlao.szkakayiduo.com`）默认连接本地后端 `http://127.0.0.1:8000`
4. 本地开发使用当前 origin

### 多模态融合引擎（核心 AI 流水线）

翡翠识别的融合逻辑在 `app/services/jade_multimodal_service.py`：

1. **YOLO 检测**（`jade_yolo_service.py`）— 器型/题材检测，置信度过滤 + 面积阈值过滤
2. **VLM 视觉分析**（`jade_vlm_service.py`）— Ollama 本地服务，提取颜色/种水/器型/题材
3. **OpenCV 图像分析** — HSV 颜色分布、轮廓形状特征、透明度纹理启发式
4. **文本上下文** — 主播语音转写 + OCR 弹幕/画面文字，关键词匹配
5. **融合策略**：YOLO/VLM/文本为主源（高权重），OpenCV 仅填补空缺字段（低权重）
6. **反馈学习**（`jade_feedback_learning_service.py`）— 人工纠正 → 规则修正

置信度计算：`app/services/jade_evaluation_service.py` 评估各源可信度。

### YOLO 实时检测与跟踪

`app/api/jade_yolo_live.py` 实现直播帧检测端点：
- ROI 裁剪后送入 YOLO（默认 ROI: 0.0, 0.12, 0.92, 0.84）
- `LiveJadeTracker` 多帧跟踪：pending → confirmed，box 平滑，丢失容忍（hold_frames）
- 默认最少置信度 0.15，确认帧数 3，丢失容忍 10 帧

YOLO 模型路径通过 `JLAO_YOLO_MODEL` 环境变量配置，默认搜索 `models/jade-yolo.pt`、`backend/models/jade-yolo.pt`，无模型时回退到预训练 `yolo11n.pt`。

### WebSocket 事件

前端通过 `/ws/sessions/{session_id}` 接收实时推送：
- `session_status` — 直播状态变更
- `transcript_segment` / `transcript_partial` — 语音转写结果
- `suggestion_created` / `suggestion_updated` — AI 建议
- `frame_snapshot` — 帧分析结果
- `live_comment_event` — 弹幕 OCR 结果
- `agent_utterance` — AI 助手话术
- `wiki_hits` — 知识库命中

## 关键环境变量

配置在 `.env`（复制自 `.env.example`）：

```env
# 数据库（默认 SQLite）
DATABASE_URL=sqlite:///data/jlao-mvp.sqlite

# GPU 加速
FUNASR_DEVICE=cuda
PADDLEOCR_USE_GPU=true
JLAO_YOLO_DEVICE=          # 留空自动检测

# YOLO 模型路径
JLAO_YOLO_MODEL=

# VLM（Ollama 本地）
JLAO_VLM_HTTP_URL=http://localhost:11434
JLAO_VLM_HTTP_MODEL=llava

# 语音转写（local = FunASR，aliyun = 阿里云 NLS）
STT_PROVIDER=local
ALIYUN_STT_APP_KEY=
ALIYUN_STT_TOKEN=

# 弹幕/翡翠 OCR 间隔
JLAO_COMMENT_OCR_INTERVAL_SECONDS=0.5
JLAO_JADE_OCR_INTERVAL_SECONDS=1.2

# OpenCV 颜色填充模式：color-water（默认）、all、none、primary-only
JLAO_JADE_OPENCV_FILL=color-water
```

## 产品定位

视频号翡翠直播间AI助手系统。为主播、观众、运营提供全链路翡翠识别与直播辅助能力。

- **主播端**：实时辅助讲货（画面识别 → 自动弹出种水/颜色/价格参考）
- **观众端**：截图识别翡翠属性，辅助购买决策
- **运营后台**：直播内容质检、主播话术合规审核

## 关键特征

- 视频号直播间为**竖屏**
- 翡翠识别维度：种水、颜色、器型、题材、瑕疵、价格评估
- 已有多模态融合引擎（YOLO + VLM + OCR + STT + OpenCV）
- 已有反馈学习闭环（弱样本收集 → 人工标注 → YOLO训练 → 评估）
- 已有14类翡翠器型YOLO检测模型

## 当前直播间

- 直播间名称：**浅玩翡翠-2号店**（固定，不跳来跳去）
- 直播间主要器型：镶嵌戒指、镶嵌吊坠、手串/珠串
- YOLO 训练集现状：只有手镯数据，其他器型缺失

## YOLO 数据收集计划

1. 连接直播间数据流 → YOLO 检测
2. 监控 2 小时，自动截图保存
3. 筛选低置信度（1%-30%）和未检测到的图
4. 人工筛选有价值的图（漏检样本）
5. AI 图生图增强（OpenAI Image-2）
6. 标注后加入训练集
7. 增量训练 YOLO

## 前端页面结构

- **自有运营（LiveDashboard）**：YOLO 视频流 + 运营数据墙
  - 顶部导航栏有"设置"按钮（scrcpy 驱动配置）
  - 主页不再显示 scrcpy 驱动面板
  - 客户线索在"其它分析"页面
- **其它分析（ObservationDashboard）**：
  - 客户线索栏目（显示真实弹幕用户名字）
  - 成交卡片、复盘骨架
  - 不再显示 scrcpy 驱动面板

## 视频号直播间手播 ROI

基于6张真实直播间截图标定，**主播手持翡翠展示**（手播）模式下，翡翠核心展示区的固定坐标：

```
x: 5%  ~ 95%   (宽度 90%)
y: 15% ~ 60%   (高度 45%)
```

**竖屏 1080×1920 换算：**
- 像素区域：x=[54, 1026], y=[288, 1056]
- ROI 面积占全图：36%
- 计算量减少：64%

**标定依据：**
- 上边界 0.15：刚好避开顶部状态栏、主播头像、店名、"礼物墙"标签
- 下边界 0.55：覆盖最大的手镯展示场景（含价签），避开弹幕区和底部购买卡片
- 左右 0.05~0.95：覆盖画面几乎全部宽度，翡翠展示区天然水平居中

**使用方式：**
- 帧提取后先按此 ROI 裁剪，再送入 YOLO/VLM 识别
- 该 ROI 仅适用于**手播**模式

## 货品面积阈值（YOLO 后处理过滤）

基于6张手播标定图，**翡翠货品占 ROI 红框**的比例如下：

| 图 | 货品 | 货品/红框 | 说明 |
|---|---|---|---|
| 1 | 两枚戒指 | ~21% | 有效 |
| 2 | 一对耳钉 | ~34% | 有效 |
| 3 | 红翡戒指 | **~15%** | **最小有效货品** |
| 4 | 紫罗兰圆牌 | ~76% | 有效 |
| 5 | 手镯（竖放）| ~11% | 个例，主播会转至平放 |
| 6 | 手镯（平放）| ~40% | 有效 |

**阈值规则：**
```
检测框面积 / 红框面积 ≥ 15% → 保留（有效翡翠）
检测框面积 / 红框面积 < 15% → 丢弃（噪声：手指、背景、UI）
```

**设定依据：**
- 图3红翡戒指（~15%）是6张图中最小的有效货品
- 图5竖放手镯（~11%）是个例，实际直播中主播会调整至平放（图6，~40%）
- 低于15%的检测目标通常是：手指关节、背景杂物、商品信息浮层、远处虚化的翡翠背景、小件配饰（如耳钉/碎钻镶嵌件）等

**应用方式：**
- YOLO 推理后，先过滤掉置信度低的框，再按面积比过滤
- 该阈值仅适用于手播 ROI 内；若更换 ROI 范围需重新标定

## 视频号直播间面播 ROI（待标定）

**面播**指主播坐在桌前，翡翠放在桌面/垫子上展示（非手持）。
- 面播的翡翠展示区通常更靠下（桌面在画面中下部）
- 面播的 ROI 范围与手播不同，**需要另外标定**
- 待用户提供面播参考图后补充数据

**推测面播特征（需验证）：**
- y 轴可能比手播更靠下（0.25~0.65 或类似）
- 桌面背景相对干净，但可能包含多件翡翠

## 识别流水线

直播画面 → 帧提取 → YOLO检测 → VLM视觉分析 → OpenCV颜色/纹理 → OCR文字 → STT语音 → 多模态融合 → 产品库自动入库 → 主播/观众展示
