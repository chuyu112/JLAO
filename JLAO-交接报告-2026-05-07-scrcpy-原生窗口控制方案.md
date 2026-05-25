# JLAO 交接报告 — 2026-05-07（scrcpy 原生窗口控制方案）

## 本次目标

将已验证可用的 `scrcpy + 手机` 投屏能力接入 JLAO，优先选择稳定可演示的方案 A：由 JLAO 后端启动和停止 scrcpy 原生窗口，前端作为投屏控制面板。

## 已完成

### 1. 后端改为控制 scrcpy 原生窗口

- 更新 `backend/app/services/scrcpy_service.py`
  - 自动查找 `scrcpy.exe`：
    - `D:\scrcpy-win64-v3.3.4\scrcpy.exe`
    - `C:\Program Files\scrcpy\scrcpy.exe`
    - Chocolatey / Scoop 常见路径
    - `PATH` 中的 `scrcpy`
  - `POST /api/sessions/{session_id}/scrcpy/start` 会启动本机 scrcpy 原生窗口。
  - `POST /api/sessions/{session_id}/scrcpy/stop` 会关闭对应 scrcpy 进程。
  - `GET /api/sessions/{session_id}/scrcpy/status` 返回运行状态。
  - 支持参数：
    - `serial`：设备序列号，可为空；为空时使用 scrcpy 默认设备。
    - `max_size`：传给 `scrcpy -m`
    - `bit_rate`：传给 `scrcpy -b`
  - 窗口标题设置为 `JLAO 投屏 - 设备序列号/默认设备`。

### 2. 前端投屏面板改为“原生窗口模式”

- 更新 `frontend/src/components/ScrcpyPanel.vue`
  - 不再连接视频 WebSocket。
  - 不再初始化 WebCodecs/Canvas 解码器。
  - 显示“scrcpy 原生窗口”模式说明。
  - 设备序列号改为可选，单设备时可直接启动。
  - 保留 localStorage 记忆上次设备序列号。

### 3. Dashboard 状态回写

- 更新 `frontend/src/pages/LiveDashboard.vue`
  - 启动成功后标记面板为已启动，并提示 `scrcpy 投屏窗口已启动`。
  - 启动失败时将后端错误写回面板。

### 4. 错误提示增强

- 更新 `frontend/src/stores/jlao.ts`
  - 优先显示 FastAPI 返回的 `detail`，避免只显示 Axios 的泛化错误。

## 已验证

- `scrcpy --help` 参数兼容性检查通过：
  - `-s / --serial`
  - `-m / --max-size`
  - `-b / --video-bit-rate`
  - `--window-title`
- 后端语法检查通过：
  - `python -m py_compile backend\app\services\scrcpy_service.py backend\app\api\scrcpy.py backend\app\schemas.py backend\app\main.py`
- 前端生产构建通过：
  - `npm.cmd run build`

## 当前使用方式

1. 启动后端和前端。
2. 进入 JLAO 直播中控台并开始直播。
3. 在左侧“手机投屏（scrcpy 原生窗口）”面板：
   - 单设备：设备序列号可留空。
   - 多设备：填写 `adb devices` 中的序列号。
4. 点击“启动投屏窗口”。
5. JLAO 会打开 scrcpy 原生窗口显示手机画面。
6. 点击“关闭投屏”可结束该 scrcpy 进程。

## 后续可选优化

1. 增加“扫描设备”按钮，直接显示 `adb devices` 列表。
2. 增加定时状态刷新，识别用户手动关闭 scrcpy 窗口后的状态变化。
3. 增加投屏参数配置：
   - 分辨率
   - 码率
   - 窗口置顶
   - 关闭手机屏幕
4. 后续如确实需要浏览器内嵌画面，再单独推进 WebCodecs/Named Pipe 方案。

