# JLAO 本地语音识别配置

当前 STT 默认切换为本地模型：

```text
STT_PROVIDER=local
```

## 安装依赖

在插手机、运行本地后端的电脑上执行：

```cmd
cd /d D:\JLAO\backend
python -m pip install -r requirements-local-stt.txt
```

## 模型配置

默认使用：

```text
LOCAL_STT_MODEL=small
LOCAL_STT_DEVICE=cpu
LOCAL_STT_COMPUTE_TYPE=int8
LOCAL_STT_LANGUAGE=zh
```

如果已经下载了本地模型目录，可指定：

```cmd
set LOCAL_STT_MODEL=D:\models\faster-whisper-small
```

然后启动后端：

```cmd
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 回退阿里云

如需临时回退阿里云：

```cmd
set STT_PROVIDER=aliyun
set ALIYUN_STT_APP_KEY=你的appkey
set ALIYUN_STT_TOKEN=你的token
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 注意

- 本地模型第一次加载会比较慢。
- `small` 模型 CPU 可用但延迟会高；后续桌面版可做模型下载和状态提示。
- 当前音频来源仍是浏览器采集的麦克风/标签页音频；手机内部声音直连还没做。
