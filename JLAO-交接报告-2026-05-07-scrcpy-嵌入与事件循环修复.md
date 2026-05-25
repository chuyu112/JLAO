# JLAO 交接报告 — 2026-05-07（scrcpy 嵌入方向）

## 一、本日已完成

### 1. scrcpy 视频流嵌入后端（已实现，链路未完全跑通）
- **新建 `backend/app/services/scrcpy_service.py`**：管理 scrcpy 生命周期。
  - 自动探测 scrcpy/adb 安装路径。
  - NALU 边界解析（`0x00 00 00 01` / `0x00 00 01`），识别 SPS(7)、PPS(8)、IDR(5)、slice(1)。
  - 缓存 SPS/PPS，关键帧前先行发送，保证前端解码器能立即初始化。
  - 通过 `scrcpy_clients` 维护 WebSocket 客户端列表，广播 binary NALU。
- **新建 `backend/app/ws/scrcpy_ws.py`**：WebSocket endpoint `/ws/sessions/{session_id}/scrcpy`。
- **新建 `backend/app/api/scrcpy.py`**：REST API `POST /start`、`POST /stop`、`GET /status`。
- **`backend/app/main.py`**：注册 scrcpy router 和 ws router。
- **`backend/app/schemas.py`**：新增 `ScrcpyStartRequest`、`ScrcpyStatus`。

### 2. scrcpy 视频流嵌入前端（已实现，解码器就绪）
- **新建 `frontend/src/utils/scrcpyDecoder.ts`**：WebCodecs H.264 解码器。
  - 解析 SPS 生成 `avc1.PPCCLL` codec string。
  - AnnexB NALU 转 avcC 格式，封装 `EncodedVideoChunk` 喂给 `VideoDecoder`。
  - `output` callback 中 `ctx.drawImage(videoFrame, 0, 0)` 渲染到 Canvas。
- **新建 `frontend/src/components/ScrcpyPanel.vue`**：设备连接配置 + Canvas 实时显示。
  - USB Serial 输入框、连接/断开按钮、状态指示。
  - WebSocket 连接 `/ws/sessions/{id}/scrcpy`，`binaryType = 'arraybuffer'`。
  - **localStorage 记忆**：自动保存/恢复上次使用的设备序列号。
- **`frontend/src/stores/jlao.ts`**：新增 `scrcpyInfo`、`scrcpyLoading`，以及 `startScrcpySession`、`stopScrcpySession`、`refreshScrcpyStatus`。
- **`frontend/src/api/jlao.ts`**：新增 `startScrcpy`、`stopScrcpy`、`getScrcpyStatus`。
- **`frontend/src/types.ts`**：新增 `ScrcpyDeviceInfo` 类型。
- **`frontend/src/pages/LiveDashboard.vue`**：左侧工作区集成 `<scrcpy-panel>`，直播中自动显示。

### 3. 已知参数兼容性修复
- scrcpy 3.3.4 移除了 `--no-display`，改为 `--no-playback`，已同步修改。

---

## 二、已验证的方案与阻塞根因

### 方案 A：scrcpy `--record=-` + FFmpeg 解封装（失败）
- **现象**：scrcpy 进程启动、推送 server、WebSocket 连接成功，但 Canvas 无画面。
- **根因**：scrcpy 的 `--record=-`（stdout）在 Windows 上无法实时输出 MKV 视频数据。
  - 手动测试：`--record=D:/test.mkv`（文件）8 秒输出 9.4MB ✅
  - 手动测试：`--record=-`（stdout）8 秒输出仅 286 字节 ❌
  - 根因：MKV 容器格式需要 seekable 输出，Windows C 运行时对 pipe 使用 block buffering，导致数据无法实时流出。
- **结论**：此方案在 Windows 上不可行，无论是否经过 FFmpeg。

### 方案 B：`adb shell screenrecord --output-format=h264 -`（失败）
- **现象**：adb 命令执行，但 stdout 为 0 字节。
- **根因**：设备上 **没有 `screenrecord` 二进制文件**（`inaccessible or not found`）。设备仅有 `screencap`。
- **结论**：此方案在该设备上不可用。

### 方案 C：`adb shell screencap`（待验证）
- **验证结果**：`screencap` 可用，输出 raw RGBA 数据（1084x2412，格式 RGBA_8888）。
- **待实现**：需构建 `screencap 循环抓取 → FFmpeg 实时编码 H.264 → WebSocket 广播 → Canvas 渲染`  pipeline。

---

## 三、当前环境状态
- **本地后端**：已更新为 `adb shell screenrecord` 方案（但设备不支持），需回退或重构为 `screencap + FFmpeg` 方案。
- **本地前端**：`npm run build` 通过，ScrcpyPanel 与解码器已就绪，只需后端供给有效视频数据即可出画面。
- **生产服务器**：尚未部署 scrcpy 相关代码。

---

## 四、明日/下次优先事项

### 首选方案：screencap + FFmpeg 实时编码
```
adb shell "while true; do screencap; sleep 0.05; done"
  → raw RGBA frames (1084x2412)
  → FFmpeg: -f rawvideo -pix_fmt rgba -s 1084x2412 -r 20 -i pipe:0
            -c:v libx264 -preset ultrafast -tune zerolatency
            -profile:v baseline -level 3.0 -f h264 pipe:1
  → H.264 NALU stream
  → WebSocket broadcast
  → WebCodecs decoder → Canvas
```
- **性能考量**：PC 端 CPU 编码 1084x2412@20fps 压力较大，可考虑降低分辨率（`adb shell wm size` 修改或 FFmpeg 缩放）。
- **Fallback**：如 H.264 编码延迟过高，可改用 MJPEG（`-c:v mjpeg -f mjpeg`），前端直接用 `<img>` 显示 JPEG 帧，绕开 WebCodecs。

### 备选方案
1. **Windows Named Pipe**：用 `ctypes` 创建 `\.	ube
ame`，让 scrcpy `--record` 写入命名管道，绕过 stdout 缓冲限制。
2. **接受桌面窗口**：直接启动 scrcpy（不加 `--no-playback`），用户通过独立窗口查看手机画面，不在浏览器内嵌入。

---

*报告更新时间：2026-05-07*
