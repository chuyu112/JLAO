# PC-B 采集链路改动记录

更新时间：2026-06-11 22:25

## 背景

这轮主要是在 PC-B 上排查和调整：

- scrcpy 投屏窗口
- 原生手机音频 STT
- 前端视频区域
- OCR / 弹幕 / 样本截图
- FunASR CPU/GPU 配置

后续讨论已经确认一个关键结论：**网页里显示的“视频流”不应该用 ADB 截图刷新来冒充，真正目标应该是 scrcpy/H264 真视频流；截图只应该服务 OCR、样本和分析。**

## 当前关键结论

1. PC-C 不卡，大概率是因为它显示的是 scrcpy 原生视频窗口或浏览器捕获投屏窗口，属于真实视频链路。
2. PC-B 后来改成的后端视频面板，是 `adb screencap -> jpg -> 文件 -> WebSocket -> img`，本质是截图预览，不是真视频流。
3. 截图预览可以用来临时看画面，但不适合作为流畅视频显示方案。
4. 正确方向应是：
   - 投屏显示走 scrcpy 真视频；
   - 前端视频区域也接真视频流；
   - OCR / 样本 / 弹幕识别单独走 1 秒一次截图；
   - STT 音频单独运行，不被视频或 OCR 拖慢。

## 后端改动

### scrcpy 启动

文件：

- `backend/app/services/scrcpy_service.py`
- `backend/tests/test_mvp_services.py`
- `.env`

改动：

- 增加 `.env` 配置控制 scrcpy：
  - `JLAO_SCRCPY_NO_WINDOW=false`
  - `JLAO_SCRCPY_ALWAYS_ON_TOP=false`
  - `JLAO_SCRCPY_NO_AUDIO=true`
  - `JLAO_SCRCPY_BIT_RATE=2M`
  - `JLAO_SCRCPY_CAPTURE_ORIENTATION=@0`
  - `JLAO_SCRCPY_MAX_FPS=20`
  - `JLAO_SCRCPY_MAX_SIZE=0`
  - `JLAO_SCRCPY_AUTO_RECORD=false`
- 去掉硬编码 `--window-x 0 --window-y 0`。
- 增加可选窗口位置配置：
  - `JLAO_SCRCPY_WINDOW_X`
  - `JLAO_SCRCPY_WINDOW_Y`
  - `JLAO_SCRCPY_WINDOW_WIDTH`
  - `JLAO_SCRCPY_WINDOW_HEIGHT`
- 明确不再默认 always-on-top，避免投屏窗口挡住网页。
- 增加 scrcpy / QtScrcpy 驱动扫描函数，支持扫描 D 盘一级目录下的驱动。
- 增加测试覆盖：
  - 不默认传 `--window-x/--window-y`
  - 配置窗口位置时才传
  - D 盘一级目录可扫描 scrcpy / QtScrcpy

### 手机截图采集

文件：

- `backend/app/services/phone_capture_service.py`
- `backend/app/api/phone_capture.py`
- `backend/app/schemas.py`
- `backend/app/services/sampling_settings.py`
- `backend/app/api/runtime_settings.py`
- `.env`

改动：

- 新增 `JLAO_PHONE_CAPTURE_ANALYZE_FRAMES=false`，PC-B 本地用于跳过重分析，减少对 STT 的影响。
- 新增 `phone_video_frame` WebSocket 事件，后端截图压缩后立即广播给前端。
- 将后端截图循环拆成两个概念：
  - `interval_seconds`：截图/OCR/样本/分析频率，默认 1 秒。
  - `preview_interval_seconds`：前端预览刷新频率，默认 0.2 秒。
- 新增 `.env`：
  - `JLAO_PHONE_CAPTURE_PREVIEW_INTERVAL_SECONDS=0.2`
  - `JLAO_CAPTURE_SAMPLE_INTERVAL_SECONDS=1.0`
  - `JLAO_PHONE_CAPTURE_INTERVAL_SECONDS=1.0`
- 设置接口 `/api/settings/sampling` 增加：
  - `configured_preview_interval_seconds`
  - `active_preview_interval_seconds`
  - `configured_preview_fps`
  - `active_preview_fps`
  - `min_preview_fps`
  - `max_preview_fps`
- 后续按“上限 30 帧”要求，源码里把预览 FPS 上限从 24 改为 30：
  - `MIN_PHONE_PREVIEW_INTERVAL_SECONDS = 1 / 30`
  - `max_preview_fps = 30`

注意：

- 这条预览仍然是 ADB 截图预览，不是真视频。
- FPS 拉高会增加 ADB 截图、压缩、文件写入和前端图片加载压力。
- 30fps 上限代码已改，但最后一次用户要求“先讨论”后未再做完整验证和后端重启确认。

### STT / 音频

文件：

- `backend/app/services/native_stt_service.py`
- `backend/app/services/local_stt_service.py`
- `backend/app/ws/stt_ws.py`

改动：

- 原生手机音频 STT 继续走 scrcpy 音频录制链路。
- 过滤 scrcpy 启动时容易误导的非错误输出，例如：
  - `No video mirroring, SDK mouse disabled`
  - `scrcpy-server: ... file pushed`
- 增加对设备断开、offline、scrcpy 可恢复错误的处理。
- 增加 WebSocket STT 正常断开场景处理，减少无意义异常。
- FunASR 设置支持在设置里切 CPU/GPU。

当前 FunASR 目标配置：

- `STT_PROVIDER=local`
- `NATIVE_STT_PROVIDER=local`
- `LOCAL_STT_ENGINE=funasr`
- `LOCAL_STT_DEVICE=cpu` 或 `cuda`
- `MODELSCOPE_CACHE=D:\JLAO\models\modelscope`

### OCR / 弹幕

文件：

- `backend/app/services/live_comment_service.py`
- `backend/app/services/jade_frame_ocr_service.py`
- `backend/app/services/paddleocr_service.py`
- `backend/app/api/jade_yolo_live.py`

改动：

- OCR / 弹幕 / 翡翠截图识别的采样间隔改成跟统一采样配置走。
- 处理了部分 OCR 行解析问题，例如昵称单独一行时拼接下一行弹幕。
- YOLO 直播识别结果构造逻辑被抽出复用，供后端截图流广播结果。

## 前端改动

### 采集启动流程

文件：

- `frontend/src/pages/LiveDashboard.vue`
- `frontend/src/pages/ObservationDashboard.vue`
- `frontend/src/stores/jlao.ts`

改动：

- `采集` 流程改为一键启动：
  - 启动/确认 scrcpy 投屏
  - 启动 Native STT
  - 启动 phone-capture 后端截图源
  - 启动前端视频面板
- 启动前会刷新后端真实状态，不再只相信前端旧状态。
- 停止采集会停止相关采集源。
- 增加定时刷新 STT 状态和实时转写数据。

### 前端视频面板

文件：

- `frontend/src/components/JadeYoloLivePanel.vue`
- `frontend/src/stores/jlao.ts`
- `frontend/src/types.ts`

改动：

- 移除了原来的浏览器 `getDisplayMedia()` 选择窗口逻辑。
- 改为接收后端 `phone_video_frame` 事件显示图片帧。
- 增加左上角实际 FPS 显示。
- FPS 当前按图片 `load` 事件计数，显示前端实际加载到的帧率。

重要问题：

- 这导致前端视频区域变成“截图预览”，不是 PC-C 那种真视频流。
- 这是当前方向上最大的问题，后续应该重构回真视频。

### 设置面板

文件：

- `frontend/src/components/SettingsPanel.vue`
- `frontend/src/api/jlao.ts`
- `frontend/src/types.ts`
- `frontend/src/stores/jlao.ts`

改动：

- 增加 FunASR CPU/GPU 选择。
- 增加采样设置接口：
  - 视频预览 FPS
  - 截图/OCR/样本间隔
- 预览 FPS 保存时改为直接传 `preview_fps`，避免保存后又回到 5fps。
- 默认预览约 5fps，源码上限后来改为 30fps。

注意：

- `SettingsPanel.vue` 原文件里已有中文编码损坏，当前页面文案部分仍可能显示乱码。
- 功能构建通过，但文案后续建议单独清理。

### UI 体验

文件：

- `frontend/src/components/SessionStatusBar.vue`

改动：

- 停止采集按钮从红色 `type="error"` 改成淡色 secondary，避免强警示风格。

## 启动脚本和日志

文件：

- `start-backend.bat`
- `scripts/start-backend.ps1`
- `scripts/start-frontend.ps1`
- `scripts/cleanup-runtime-residue.ps1`
- `backend/app/services/startup_cleanup_service.py`

改动：

- 后端启动时增加 runtime residue 清理。
- 后端日志不隐藏，保留后端窗口输出。
- 增加清理 adb/scrcpy 残留进程和端口的脚本能力。

## 验证记录

已经执行并通过过的检查：

- `backend\.venv\Scripts\python.exe -m py_compile ...`
- `backend\.venv\Scripts\python.exe -m unittest backend.tests.test_mvp_services.ScrcpyCommandTests`
- `npm.cmd run build`
- `http://127.0.0.1:8000/docs` 返回 200

注意：

- 最后一次把 FPS 上限从 24 改 30 后，没有再完整跑一轮构建和后端重启确认。

## 当前运行/配置状态

当前 `.env` 相关值：

```env
JLAO_SCRCPY_NO_WINDOW=false
JLAO_SCRCPY_ALWAYS_ON_TOP=false
JLAO_SCRCPY_NO_AUDIO=true
JLAO_SCRCPY_BIT_RATE=2M
JLAO_SCRCPY_VIDEO_ENCODER=
JLAO_SCRCPY_CAPTURE_ORIENTATION=@0
JLAO_SCRCPY_MAX_FPS=20
JLAO_SCRCPY_MAX_SIZE=0
JLAO_SCRCPY_WINDOW_X=
JLAO_SCRCPY_WINDOW_Y=
JLAO_SCRCPY_WINDOW_WIDTH=
JLAO_SCRCPY_WINDOW_HEIGHT=
JLAO_SCRCPY_AUTO_RECORD=false
JLAO_PHONE_CAPTURE_ANALYZE_FRAMES=false
JLAO_PHONE_CAPTURE_PREVIEW_INTERVAL_SECONDS=0.2
JLAO_CAPTURE_SAMPLE_INTERVAL_SECONDS=1.0
JLAO_PHONE_CAPTURE_INTERVAL_SECONDS=1.0
```

## 已知问题

1. 网页视频区域当前不是“真视频流”，而是 ADB 截图预览。
2. 这解释了为什么 PC-C 不卡、PC-B 网页视频区域会卡。
3. FPS 角标如果显示低，不一定是前端问题，可能是后端截图/压缩/文件加载链路本身跟不上。
4. 设置面板存在中文乱码，建议后续单独整理。
5. true scrcpy/H264 视频流尚未真正实现。
6. `frontend/src/utils/scrcpyDecoder.ts` 和 `/ws/sessions/{session_id}/scrcpy` 目前看起来像半成品/占位：
   - 前端 decoder 未实际接入页面。
   - 后端 WebSocket 只注册 client，没有把 scrcpy H264 stdout 推给前端。

## 建议下一步

正确重构方向：

1. 保留 scrcpy 可见投屏窗口，用于人工观察。
2. 网页视频区域接真视频源：
   - 优先方案：后端启动 scrcpy headless H264 输出，WebSocket 推给前端，前端 WebCodecs 解码。
   - 备选方案：恢复浏览器捕获 scrcpy 窗口，但用户体验上需要选择窗口。
3. phone-capture 只保留给 OCR/样本/弹幕，默认 1 秒一次。
4. STT 独立运行，不与视频/OCR互相 stop/start。
5. 设置里明确区分：
   - 视频预览帧率
   - 截图/OCR/样本频率
   - STT 设备 CPU/GPU

不建议继续做：

- 把 ADB 截图预览硬拉到 30fps 来当视频流。
- 让 OCR、样本保存、视频显示共用一个截图频率。
- 用 always-on-top 解决窗口捕获问题。
