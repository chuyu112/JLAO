import asyncio
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

import websockets
from websockets import WebSocketClientProtocol

ALIYUN_STT_URL = os.getenv("ALIYUN_STT_URL", "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1")
ALIYUN_STT_APP_KEY = os.getenv("ALIYUN_STT_APP_KEY", "")
ALIYUN_STT_TOKEN = os.getenv("ALIYUN_STT_TOKEN", "")
ALIYUN_AK_ID = os.getenv("ALIYUN_AK_ID") or os.getenv("ALIYUN_ACCESS_KEY_ID", "")
ALIYUN_AK_SECRET = os.getenv("ALIYUN_AK_SECRET") or os.getenv("ALIYUN_ACCESS_KEY_SECRET", "")
ALIYUN_STT_SAMPLE_RATE = int(os.getenv("ALIYUN_STT_SAMPLE_RATE", "16000"))
ALIYUN_STT_TOKEN_REFRESH_SECONDS = int(os.getenv("ALIYUN_STT_TOKEN_REFRESH_SECONDS", "300"))

logger = logging.getLogger(__name__)
_cached_token = ""
_cached_token_expires_at = 0
_token_lock = asyncio.Lock()


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
        return bool(ALIYUN_STT_APP_KEY and (ALIYUN_STT_TOKEN or (ALIYUN_AK_ID and ALIYUN_AK_SECRET)))

    async def connect(self) -> None:
        if not self.configured:
            raise AliyunSttNotConfigured(
                "阿里云实时语音识别未配置：需要 ALIYUN_STT_APP_KEY，并配置 ALIYUN_STT_TOKEN 或 ALIYUN_AK_ID/ALIYUN_AK_SECRET"
            )

        token = await _get_aliyun_token()
        self.websocket = await websockets.connect(
            f"{ALIYUN_STT_URL}?token={token}",
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


async def _get_aliyun_token() -> str:
    if ALIYUN_STT_TOKEN:
        return ALIYUN_STT_TOKEN

    if not (ALIYUN_AK_ID and ALIYUN_AK_SECRET):
        raise AliyunSttNotConfigured("阿里云 NLS token 未配置：缺少 ALIYUN_AK_ID/ALIYUN_AK_SECRET")

    global _cached_token, _cached_token_expires_at
    now = int(time.time())
    if _cached_token and _cached_token_expires_at - ALIYUN_STT_TOKEN_REFRESH_SECONDS > now:
        return _cached_token

    async with _token_lock:
        now = int(time.time())
        if _cached_token and _cached_token_expires_at - ALIYUN_STT_TOKEN_REFRESH_SECONDS > now:
            return _cached_token

        token, expires_at = await asyncio.to_thread(_create_aliyun_token)
        _cached_token = token
        _cached_token_expires_at = expires_at
        return _cached_token


def _create_aliyun_token() -> tuple[str, int]:
    try:
        from aliyunsdkcore.acs_exception.exceptions import ClientException, ServerException
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.http import protocol_type
        from aliyunsdkcore.request import CommonRequest
    except ImportError as exc:
        raise AliyunSttNotConfigured("缺少 aliyun-python-sdk-core，无法自动获取阿里云 NLS token") from exc

    client = AcsClient(ALIYUN_AK_ID, ALIYUN_AK_SECRET, "cn-shanghai")
    request = CommonRequest()
    request.set_method("POST")
    request.set_protocol_type(protocol_type.HTTPS)
    request.set_domain("nls-meta.cn-shanghai.aliyuncs.com")
    request.set_version("2019-02-28")
    request.set_action_name("CreateToken")

    try:
        response = client.do_action_with_exception(request)
    except (ClientException, ServerException) as exc:
        raise AliyunSttNotConfigured(f"获取阿里云 NLS token 失败：{exc}") from exc

    payload = json.loads(response.decode("utf-8") if isinstance(response, bytes) else response)
    token_payload = payload.get("Token") or {}
    token = token_payload.get("Id") or ""
    expires_at = int(token_payload.get("ExpireTime") or 0)
    if not token or not expires_at:
        raise AliyunSttNotConfigured(f"阿里云 NLS token 响应无效：{payload}")
    return token, expires_at
