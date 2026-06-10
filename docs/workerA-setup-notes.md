# WorkerA 配置与问题排查记录

> 记录日期：2026-06-07
> WorkerA 使用开源 FunASR，WorkerB 使用阿里云

---

## 一、语音识别（STT）配置

### 环境变量（`.env`）

```bash
STT_PROVIDER=local
LOCAL_STT_ENGINE=funasr
LOCAL_STT_DEVICE=cuda
LOCAL_STT_SAMPLE_RATE=16000
LOCAL_STT_CHUNK_SECONDS=4
```

### Native STT（手机原生音频）

- 音频源：scrcpy `--audio-source=voice-performance`
- 识别引擎：FunASR `paraformer-zh`（本地 CPU/GPU）
- 默认 provider 保持 `aliyun`（兼容 WorkerB），WorkerA 通过 `.env` 覆盖为 `local`

### 关键代码修改

**`backend/app/services/native_stt_service.py`**
- 新增 `_NATIVE_STT_PROVIDER` 环境变量读取
- `_create_native_stt()` 根据 provider 选择 `AliyunRealtimeStt` 或 `LocalChunkStt`
- `NativeSttTaskState.provider` 动态化
- **注意**：`_NATIVE_STT_PROVIDER` 必须定义在 `NativeSttTaskState` 类之前（Python dataclass 默认值在类定义时求值）

**`frontend/src/pages/LiveDashboard.vue`**
- `handleStart()` 中去掉 `if (store.scrcpyInfo?.running)` 条件
- 直接 `try { await store.startNativeSttSession() }` 自动启动 Native STT

---

## 二、已修复的 Bug

### 1. NameError: _NATIVE_STT_PROVIDER

**现象**：后端启动失败，报错 `_NATIVE_STT_PROVIDER` 未定义。

**原因**：`_NATIVE_STT_PROVIDER` 定义在 `NativeSttTaskState` dataclass 之后，而 dataclass 默认值在类定义时就求值。

**修复**：将 `_NATIVE_STT_PROVIDER` 移到 `NativeSttTaskState` 类定义之前。

### 2. 前端不自动启动 Native STT

**现象**：点击"启动采集"后，Native STT 没有启动，转写结果全是噪音（"the the the"）。

**原因**：`handleStart()` 中判断 `if (store.scrcpyInfo?.running)`，但视频投屏进程返回状态有延迟/异常，导致条件为 false，跳过了 Native STT 启动。

**修复**：去掉条件判断，直接尝试启动 Native STT。

### 3. 按钮"点不了采集"

**现象**："启动采集"按钮灰色或点击无反应。

**原因**："其它分析"页面有采集会话在运行（`live-7e88fbc0b238`），阻塞了"自有直播间运营"模式。

**解决**：先去"其它分析"页面停止采集，或从后端停止对应 session 的 scrcpy/phone-capture。

### 4. 手机截屏超时

**现象**：日志大量出现 `"手机截屏超时，请确认设备已连接并授权 USB 调试。"`

**原因**：USB 连接不稳定，或 adb 授权失效。

**解决**：
1. 检查手机 USB 调试是否开启
2. 重新插拔数据线
3. 执行 `adb devices` 确认设备在线

---

## 三、部署流程

### 前端构建与上传

```bash
cd D:\JLAO\frontend
npm install @ffmpeg/ffmpeg  # 如果缺失
npm run build
scp -r D:\JLAO\frontend\dist\* root@47.120.41.143:/var/www/jlao/
```

### 后端启动

```bash
cd D:\JLAO\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

或使用 `start-backend.bat`（带日志和自动重启）。

---

## 四、常见问题速查

| 问题 | 排查方向 |
|---|---|
| 转写全是 "the the the" | 前端走的是 WebSocket STT（浏览器噪音），不是 Native STT。检查 Native STT 是否启动。 |
| 找不到投屏窗口 | 1. scrcpy 窗口可能被遮挡，按 Alt+Tab 找；2. 浏览器选择框切换到"窗口"选项卡；3. 重新启动采集。 |
| 按钮点不了 | "其它分析"页面可能有采集在运行，先停止它。 |
| 后端启动失败 | 检查 `native_stt_service.py` 中 `_NATIVE_STT_PROVIDER` 是否在 `NativeSttTaskState` 之前定义。 |
| YOLO 检测不工作 | 检查 `models/jade-yolo.pt` 是否存在；后端 health 是否正常。 |

---

## 五、WorkerA vs WorkerB 差异

| 项目 | WorkerA | WorkerB |
|---|---|---|
| STT Provider | `local` (FunASR) | `aliyun` |
| 本地模型 | `paraformer-zh` | 无 |
| 前端代码 | 同一份，通过环境变量切换 | 同一份 |
| 手机音频采集 | scrcpy `--audio-source=voice-performance` | 同上 |
| 阿里云 Key | 无 | 已配置 |
