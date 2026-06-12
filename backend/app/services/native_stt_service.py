from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from app.services import native_audio_service
from app.services.native_audio_service import (
    _adb_exe_for_scrcpy,
    _build_audio_record_command,
    _find_wav_data_offset,
    _is_device_disconnected_error,
    _is_scrcpy_recoverable_error,
    _recover_adb_device,
    _wav_to_pcm16_mono_16k,
)
from app.services.transcript_service import append_transcript
from app.state import app_state
from app.ws.manager import manager

logger = logging.getLogger(__name__)

_LOCAL_STT_FRAME_SIZE = 640
_STT_AUDIO_QUEUE_MAX_CHUNKS = 120


@dataclass
class NativeSttTaskState:
    session_id: str
    serial: str
    chunk_seconds: int
    task: asyncio.Task[None] | None = None
    running: bool = True
    provider: str = "local"
    last_error: str = ""
    audio_chunks: int = 0
    audio_bytes: int = 0
    transcript_segments: int = 0
    queue: asyncio.Queue[bytes] = field(default_factory=lambda: asyncio.Queue(maxsize=_STT_AUDIO_QUEUE_MAX_CHUNKS))


native_stt_tasks: dict[str, NativeSttTaskState] = {}
_DEFAULT_NATIVE_STT_DEVICE_KEY = "__default__"


def _native_stt_provider() -> str:
    from app.services.runtime_settings_service import get_stt_provider

    return get_stt_provider()


def _create_native_stt(provider: str, on_partial, on_final, on_error):
    if provider == "aliyun":
        from app.services.aliyun_stt_service import AliyunRealtimeStt

        return AliyunRealtimeStt(on_partial=on_partial, on_final=on_final, on_error=on_error)

    from app.services.local_stt_service import LocalChunkStt
    return LocalChunkStt(on_partial=on_partial, on_final=on_final, on_error=on_error)


async def initialize_native_stt_runtime() -> None:
    logger.info("[native-stt] startup reset: clearing STT task state")
    native_stt_tasks.clear()


def _native_stt_device_key(serial: str) -> str:
    return serial.strip() or _DEFAULT_NATIVE_STT_DEVICE_KEY


def _sessions_for_native_stt_device(serial: str) -> list[str]:
    key = _native_stt_device_key(serial)
    return [
        session_id
        for session_id, task_state in native_stt_tasks.items()
        if _native_stt_device_key(task_state.serial) == key
    ]


async def _stop_native_stt_tasks_for_device(serial: str, except_session_id: str = "") -> None:
    for active_session_id in list(_sessions_for_native_stt_device(serial)):
        if active_session_id != except_session_id:
            await stop_native_stt(active_session_id)


async def start_native_stt(session_id: str, serial: str = "", chunk_seconds: int = 0) -> dict[str, Any]:
    if session_id not in app_state.sessions:
        raise ValueError("直播会话不存在")
    if not native_audio_service.is_running(session_id):
        raise RuntimeError("请先打开音频接入")

    cleaned_serial = serial.strip()
    await _stop_native_stt_tasks_for_device(cleaned_serial, except_session_id=session_id)
    await stop_native_stt(session_id)
    task_state = NativeSttTaskState(
        session_id=session_id,
        serial=cleaned_serial,
        chunk_seconds=chunk_seconds,
        provider=_native_stt_provider(),
    )
    native_stt_tasks[session_id] = task_state
    task_state.task = asyncio.create_task(_native_stt_loop(session_id))
    logger.info("[native-stt %s] starting; audio stream must already be connected", session_id)
    return status(session_id)


async def stop_native_stt(session_id: str) -> dict[str, Any]:
    task_state = native_stt_tasks.get(session_id)
    if task_state:
        logger.info("[native-stt %s] stopping", session_id)
        task_state.running = False
        if task_state.task and not task_state.task.done():
            task_state.task.cancel()
            try:
                await task_state.task
            except asyncio.CancelledError:
                pass
        native_stt_tasks.pop(session_id, None)
    return status(session_id)


def status(session_id: str) -> dict[str, Any]:
    task_state = native_stt_tasks.get(session_id)
    if not task_state:
        return {
            "running": False,
            "state": "stopped",
            "serial": "",
            "provider": _native_stt_provider(),
            "last_error": "",
            "audio_chunks": 0,
            "audio_bytes": 0,
            "transcript_segments": 0,
        }
    task_running = bool(task_state.task and not task_state.task.done())
    running = task_state.running and task_running
    return {
        "running": running,
        "state": "running" if running else ("error" if task_state.last_error else "stopped"),
        "serial": task_state.serial,
        "provider": task_state.provider,
        "last_error": task_state.last_error,
        "audio_chunks": task_state.audio_chunks,
        "audio_bytes": task_state.audio_bytes,
        "transcript_segments": task_state.transcript_segments,
    }


async def _native_stt_loop(session_id: str) -> None:
    task_state = native_stt_tasks[session_id]
    consumer_id = f"stt:{session_id}"

    async def on_partial(text: str) -> None:
        logger.debug("[native-stt %s] partial: %s", session_id, text)
        await manager.broadcast(session_id, "transcript_partial", {"text": text})

    async def on_final(text: str) -> None:
        logger.info("[native-stt %s] final: %s", session_id, text)
        segment = await append_transcript(session_id, text)
        task_state.transcript_segments += 1
        await manager.broadcast(session_id, "transcript_segment", segment.model_dump(mode="json"))
        await manager.broadcast(session_id, "transcript_partial", {"text": ""})

    async def on_error(message: str) -> None:
        logger.warning("[native-stt %s] error: %s", session_id, message)
        task_state.last_error = message
        await manager.broadcast(session_id, "stt_error", {"message": message})

    async def enqueue_audio(pcm: bytes) -> None:
        if not task_state.running:
            return
        frame = bytes(pcm)
        try:
            task_state.queue.put_nowait(frame)
        except asyncio.QueueFull:
            try:
                task_state.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            task_state.queue.put_nowait(frame)

    stt = _create_native_stt(task_state.provider, on_partial=on_partial, on_final=on_final, on_error=on_error)
    try:
        await stt.connect()
        task_state.last_error = ""
        native_audio_service.subscribe_audio_frames(session_id, consumer_id, enqueue_audio)
        logger.info("[native-stt %s] STT connected provider=%s", session_id, task_state.provider)
        await manager.broadcast(session_id, "stt_status", {"status": "connected", "provider": task_state.provider, "source": "native-audio"})
        await manager.broadcast(session_id, "native_stt_status", status(session_id))

        while task_state.running:
            if not native_audio_service.is_running(session_id):
                raise RuntimeError("音频接入已断开，语音识别已停止")
            try:
                pcm = await asyncio.wait_for(task_state.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if not pcm:
                continue
            task_state.audio_chunks += 1
            task_state.audio_bytes += len(pcm)
            task_state.last_error = ""
            await _send_pcm_frames(stt, pcm)
            await manager.broadcast(session_id, "native_stt_status", status(session_id))
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        task_state.running = False
        task_state.last_error = f"原生手机音频转写失败：{exc}"
        logger.error("[native-stt %s] failed: %s", session_id, task_state.last_error)
        await manager.broadcast(session_id, "stt_error", {"message": task_state.last_error})
        await manager.broadcast(session_id, "native_stt_status", status(session_id))
    finally:
        task_state.running = False
        native_audio_service.unsubscribe_audio_frames(session_id, consumer_id)
        await stt.close()
        await manager.broadcast(session_id, "stt_status", {"status": "closed", "provider": task_state.provider, "source": "native-audio"})
        await manager.broadcast(session_id, "native_stt_status", status(session_id))


async def _send_pcm_frames(stt: Any, pcm: bytes) -> None:
    frame_size = _LOCAL_STT_FRAME_SIZE
    for offset in range(0, len(pcm), frame_size):
        await stt.send_audio(pcm[offset : offset + frame_size])
