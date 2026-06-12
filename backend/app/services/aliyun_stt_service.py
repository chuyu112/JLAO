from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4


logger = logging.getLogger(__name__)

ALIYUN_STT_URL = os.getenv("ALIYUN_STT_URL", "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1")
ALIYUN_STT_APP_KEY = os.getenv("ALIYUN_STT_APP_KEY", "").strip()
ALIYUN_STT_TOKEN = os.getenv("ALIYUN_STT_TOKEN", "").strip()
ALIYUN_STT_SAMPLE_RATE = int(os.getenv("ALIYUN_STT_SAMPLE_RATE", "16000"))
ALIYUN_STT_FORMAT = os.getenv("ALIYUN_STT_FORMAT", "pcm").strip() or "pcm"
ALIYUN_STT_MAX_SENTENCE_SILENCE = int(os.getenv("ALIYUN_STT_MAX_SENTENCE_SILENCE", "800"))
ALIYUN_STT_START_TIMEOUT_SECONDS = float(os.getenv("ALIYUN_STT_START_TIMEOUT_SECONDS", "8"))


class AliyunSttNotConfigured(RuntimeError):
    pass


def normalize_stt_provider(value: str | None) -> str:
    provider = (value or "local").strip().lower()
    if provider in {"aliyun", "ali", "nls"}:
        return "aliyun"
    return "local"


class AliyunRealtimeStt:
    def __init__(
        self,
        on_partial: Callable[[str], Awaitable[None]],
        on_final: Callable[[str], Awaitable[None]],
        on_error: Callable[[str], Awaitable[None]],
    ) -> None:
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_error = on_error
        self._websocket: Any = None
        self._receiver_task: asyncio.Task[None] | None = None
        self._send_lock = asyncio.Lock()
        self._started = asyncio.Event()
        self._closed = False
        self._task_id = uuid4().hex
        self._last_partial = ""
        self._last_final = ""

    async def connect(self) -> None:
        if not ALIYUN_STT_APP_KEY or not ALIYUN_STT_TOKEN:
            raise AliyunSttNotConfigured("阿里云语音识别未配置：请填写 ALIYUN_STT_APP_KEY 和 ALIYUN_STT_TOKEN")

        self._websocket = await _connect_websocket(ALIYUN_STT_URL, ALIYUN_STT_TOKEN)
        self._receiver_task = asyncio.create_task(self._receive_loop())
        await self._send_json(_build_start_transcription_message(ALIYUN_STT_APP_KEY, self._task_id))
        try:
            await asyncio.wait_for(self._started.wait(), timeout=ALIYUN_STT_START_TIMEOUT_SECONDS)
        except asyncio.TimeoutError as exc:
            await self.close()
            raise RuntimeError("等待阿里云语音识别启动超时") from exc

    async def send_audio(self, chunk: bytes) -> None:
        if self._closed or not chunk or self._websocket is None:
            return
        async with self._send_lock:
            try:
                await self._websocket.send(chunk)
            except Exception as exc:
                await self._handle_error(f"阿里云语音识别音频发送失败：{exc}")

    async def close(self) -> None:
        self._closed = True
        websocket = self._websocket
        if websocket is not None:
            try:
                await self._send_json(_build_stop_transcription_message(ALIYUN_STT_APP_KEY, self._task_id))
            except Exception:
                pass
            try:
                await websocket.close()
            except Exception:
                pass
        if self._receiver_task and not self._receiver_task.done():
            self._receiver_task.cancel()
            try:
                await self._receiver_task
            except asyncio.CancelledError:
                pass
        self._websocket = None

    async def _send_json(self, payload: dict[str, Any]) -> None:
        if self._websocket is None:
            raise RuntimeError("阿里云语音识别连接未建立")
        await self._websocket.send(json.dumps(payload, ensure_ascii=False))

    async def _receive_loop(self) -> None:
        try:
            async for message in self._websocket:
                if isinstance(message, bytes):
                    continue
                await self._handle_message(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not self._closed:
                await self._handle_error(f"阿里云语音识别连接断开：{exc}")

    async def _handle_message(self, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.debug("[aliyun-stt] non-json message: %s", message[:200])
            return

        header = data.get("header") if isinstance(data, dict) else {}
        payload = data.get("payload") if isinstance(data, dict) else {}
        if not isinstance(header, dict):
            header = {}
        if not isinstance(payload, dict):
            payload = {}

        name = str(header.get("name") or "")
        status = header.get("status")
        if status not in (None, 20000000, "20000000"):
            message_text = str(header.get("status_text") or payload.get("status_text") or name or "阿里云语音识别异常")
            await self._handle_error(message_text)
            return

        if name == "TranscriptionStarted":
            self._started.set()
            return
        if name == "TranscriptionResultChanged":
            text = _extract_result_text(payload)
            if text and text != self._last_partial:
                self._last_partial = text
                await self.on_partial(text)
            return
        if name == "SentenceEnd":
            text = _extract_result_text(payload)
            if text and text != self._last_final:
                self._last_final = text
                self._last_partial = ""
                await self.on_final(text)
                await self.on_partial("")
            return
        if name == "TaskFailed":
            await self._handle_error(str(header.get("status_text") or payload.get("status_text") or "阿里云语音识别任务失败"))
            return
        if name == "TranscriptionCompleted":
            self._closed = True

    async def _handle_error(self, message: str) -> None:
        logger.warning("[aliyun-stt] %s", message)
        await self.on_error(message)


async def _connect_websocket(url: str, token: str) -> Any:
    import websockets

    headers = {"X-NLS-Token": token}
    kwargs = {
        "ping_interval": 20,
        "ping_timeout": 20,
        "max_size": 8 * 1024 * 1024,
    }
    ssl_context = _ssl_context()
    if ssl_context is not None:
        kwargs["ssl"] = ssl_context
    try:
        return await websockets.connect(url, additional_headers=headers, **kwargs)
    except TypeError:
        return await websockets.connect(url, extra_headers=headers, **kwargs)


def _ssl_context() -> ssl.SSLContext | None:
    if not ALIYUN_STT_URL.lower().startswith("wss://"):
        return None
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _build_start_transcription_message(appkey: str, task_id: str) -> dict[str, Any]:
    return {
        "header": {
            "appkey": appkey,
            "namespace": "SpeechTranscriber",
            "name": "StartTranscription",
            "task_id": task_id,
            "message_id": uuid4().hex,
        },
        "payload": {
            "format": ALIYUN_STT_FORMAT,
            "sample_rate": ALIYUN_STT_SAMPLE_RATE,
            "enable_intermediate_result": True,
            "enable_punctuation_prediction": True,
            "enable_inverse_text_normalization": True,
            "max_sentence_silence": ALIYUN_STT_MAX_SENTENCE_SILENCE,
        },
    }


def _build_stop_transcription_message(appkey: str, task_id: str) -> dict[str, Any]:
    return {
        "header": {
            "appkey": appkey,
            "namespace": "SpeechTranscriber",
            "name": "StopTranscription",
            "task_id": task_id,
            "message_id": uuid4().hex,
        },
        "payload": {},
    }


def _extract_result_text(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        text = result.get("text") or result.get("result")
        if isinstance(text, str):
            return text.strip()
    return ""
