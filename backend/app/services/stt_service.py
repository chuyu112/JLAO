import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from uuid import uuid4

import websockets
from websockets import WebSocketClientProtocol

ALIYUN_STT_URL = os.getenv("ALIYUN_STT_URL", "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1")
ALIYUN_STT_APP_KEY = os.getenv("ALIYUN_STT_APP_KEY", "")
ALIYUN_STT_TOKEN = os.getenv("ALIYUN_STT_TOKEN", "")
ALIYUN_STT_SAMPLE_RATE = int(os.getenv("ALIYUN_STT_SAMPLE_RATE", "16000"))

logger = logging.getLogger(__name__)


class AliyunSttNotConfigured(RuntimeError):
    pass


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
        self.websocket: WebSocketClientProtocol | None = None
        self.reader_task: asyncio.Task | None = None
        self.last_final_text = ""
        self.task_id = uuid4().hex
        self.started = asyncio.Event()

    @property
    def configured(self) -> bool:
        return bool(ALIYUN_STT_APP_KEY and ALIYUN_STT_TOKEN)

    async def connect(self) -> None:
        if not self.configured:
            raise AliyunSttNotConfigured("阿里云实时语音识别未配置：需要 ALIYUN_STT_APP_KEY 和 ALIYUN_STT_TOKEN")

        self.websocket = await websockets.connect(
            f"{ALIYUN_STT_URL}?token={ALIYUN_STT_TOKEN}",
            ping_interval=20,
            ping_timeout=20,
            max_size=8 * 1024 * 1024,
        )
        self.reader_task = asyncio.create_task(self._read_messages())
        await self.websocket.send(json.dumps(self._start_payload(), ensure_ascii=False))
        await asyncio.wait_for(self.started.wait(), timeout=8)

    async def send_audio(self, chunk: bytes) -> None:
        if self.websocket and chunk and self.started.is_set():
            await self.websocket.send(chunk)

    async def close(self) -> None:
        if self.websocket:
            try:
                await self.websocket.send(json.dumps(self._stop_payload(), ensure_ascii=False))
            except Exception:
                pass
        if self.reader_task:
            self.reader_task.cancel()
        if self.websocket:
            await self.websocket.close()
        self.websocket = None

    async def _read_messages(self) -> None:
        if not self.websocket:
            return
        async for raw_message in self.websocket:
            if not isinstance(raw_message, str):
                continue
            logger.info("Aliyun STT message: %s", raw_message)
            message = json.loads(raw_message)
            header = message.get("header", {})
            payload = message.get("payload", {})
            event = header.get("name")
            status = header.get("status")
            status_text = header.get("status_text") or header.get("statusText") or ""

            if status and status != 20000000:
                await self.on_error(status_text or f"阿里云语音识别错误：{status}")
                continue
            if event == "TranscriptionStarted":
                self.started.set()
                continue
            if event == "TaskFailed":
                await self.on_error(status_text or "阿里云实时语音识别任务失败")
                continue

            text = payload.get("result") or payload.get("text") or ""
            if not text:
                continue
            if event == "TranscriptionResultChanged":
                await self.on_partial(text)
            elif event in {"SentenceEnd", "TranscriptionCompleted"} and text != self.last_final_text:
                self.last_final_text = text
                await self.on_final(text)

    def _header(self, name: str) -> dict:
        return {
            "appkey": ALIYUN_STT_APP_KEY,
            "namespace": "SpeechTranscriber",
            "name": name,
            "task_id": self.task_id,
            "message_id": uuid4().hex,
        }

    def _start_payload(self) -> dict:
        return {
            "header": self._header("StartTranscription"),
            "payload": {
                "format": "pcm",
                "sample_rate": ALIYUN_STT_SAMPLE_RATE,
                "enable_intermediate_result": True,
                "enable_punctuation_prediction": True,
                "enable_inverse_text_normalization": True,
            },
        }

    def _stop_payload(self) -> dict:
        return {
            "header": self._header("StopTranscription"),
            "payload": {},
        }
