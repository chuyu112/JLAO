from __future__ import annotations

import asyncio
import logging
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import imageio_ffmpeg

from app.repositories import save_capture_archive
from app.schemas import CaptureArchiveItem
from app.services import native_audio_service
from app.state import WORKSPACE_DIR, app_state
from app.ws.manager import manager

logger = logging.getLogger(__name__)


@dataclass
class RecordingTaskState:
    session_id: str
    state: str
    running: bool
    audio_path: Path
    video_path: Path | None = None
    output_path: Path | None = None
    output_url: str = ""
    last_error: str = ""
    started_at: float = 0.0
    stopped_at: float = 0.0
    audio_chunks: int = 0
    audio_bytes: int = 0
    wav_file: wave.Wave_write | None = None
    audio_lock: asyncio.Lock | None = None


recording_tasks: dict[str, RecordingTaskState] = {}
_PCM_SAMPLE_RATE = 16000
_PCM_CHANNELS = 1
_PCM_SAMPLE_WIDTH = 2


async def start_recording(session_id: str) -> dict[str, Any]:
    if session_id not in app_state.sessions:
        raise ValueError("直播会话不存在")
    from app.services import capture_resource_service

    capture_resource_service.require_browser_video_running(session_id)
    if not native_audio_service.is_running(session_id):
        raise RuntimeError("请先打开音频接入")

    await stop_recording(session_id, abort=True)
    upload_dir = WORKSPACE_DIR / "uploads" / "recordings" / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    audio_path = upload_dir / f"recording-{stamp}.wav"
    wav_file = wave.open(str(audio_path), "wb")
    wav_file.setnchannels(_PCM_CHANNELS)
    wav_file.setsampwidth(_PCM_SAMPLE_WIDTH)
    wav_file.setframerate(_PCM_SAMPLE_RATE)

    state = RecordingTaskState(
        session_id=session_id,
        state="running",
        running=True,
        audio_path=audio_path,
        started_at=time.time(),
        wav_file=wav_file,
        audio_lock=asyncio.Lock(),
    )
    recording_tasks[session_id] = state

    async def write_audio(pcm: bytes) -> None:
        current = recording_tasks.get(session_id)
        if not current or not current.running or not current.wav_file or not current.audio_lock:
            return
        async with current.audio_lock:
            if current.running and current.wav_file:
                current.wav_file.writeframes(pcm)
                current.audio_chunks += 1
                current.audio_bytes += len(pcm)

    native_audio_service.subscribe_audio_frames(session_id, _consumer_id(session_id), write_audio)
    logger.info("[recorder %s] started audio=%s", session_id, audio_path)
    await manager.broadcast(session_id, "recorder_status", status(session_id))
    return status(session_id)


async def finish_recording(session_id: str, video_bytes: bytes, filename: str = "recording.webm") -> dict[str, Any]:
    state = recording_tasks.get(session_id)
    if not state:
        raise RuntimeError("录屏没有启动")
    await _stop_audio_writer(state)
    state.video_path = _recording_dir(session_id) / _safe_video_name(filename)
    state.video_path.write_bytes(video_bytes)
    if not video_bytes:
        state.state = "error"
        state.last_error = "录屏视频文件为空"
        await manager.broadcast(session_id, "recorder_status", status(session_id))
        return status(session_id)

    try:
        output_path = state.video_path.with_suffix(".mp4")
        await _merge_video_audio(state.video_path, state.audio_path, output_path)
        state.output_path = output_path
        state.output_url = _public_recording_url(session_id, output_path)
        state.state = "stopped"
        state.last_error = ""
        _archive_recording(session_id, state)
        logger.info("[recorder %s] finished output=%s", session_id, output_path)
    except Exception as exc:
        state.state = "error"
        state.last_error = f"录屏合成失败，已保留临时音视频文件：{exc}"
        logger.error("[recorder %s] merge failed: %s", session_id, exc)
    await manager.broadcast(session_id, "recorder_status", status(session_id))
    return status(session_id)


async def stop_recording(session_id: str, *, abort: bool = False) -> dict[str, Any]:
    state = recording_tasks.get(session_id)
    if not state:
        return status(session_id)
    await _stop_audio_writer(state)
    if abort:
        state.state = "stopped"
        state.last_error = ""
        recording_tasks.pop(session_id, None)
    await manager.broadcast(session_id, "recorder_status", status(session_id))
    return status(session_id)


def status(session_id: str) -> dict[str, Any]:
    state = recording_tasks.get(session_id)
    if not state:
        return {
            "running": False,
            "state": "stopped",
            "last_error": "",
            "audio_chunks": 0,
            "audio_bytes": 0,
            "output_path": "",
            "audio_path": "",
            "video_path": "",
        }
    return {
        "running": state.running,
        "state": state.state,
        "last_error": state.last_error,
        "audio_chunks": state.audio_chunks,
        "audio_bytes": state.audio_bytes,
        "output_path": state.output_url,
        "audio_path": str(state.audio_path),
        "video_path": str(state.video_path or ""),
    }


async def _stop_audio_writer(state: RecordingTaskState) -> None:
    if not state.running and not state.wav_file:
        return
    state.running = False
    state.stopped_at = time.time()
    native_audio_service.unsubscribe_audio_frames(state.session_id, _consumer_id(state.session_id))
    if state.audio_lock:
        async with state.audio_lock:
            if state.wav_file:
                state.wav_file.close()
                state.wav_file = None


async def _merge_video_audio(video_path: Path, audio_path: Path, output_path: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg,
        "-nostdin",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        message = (stderr or stdout).decode("utf-8", errors="ignore").strip()
        raise RuntimeError(message or f"ffmpeg exited {process.returncode}")
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("ffmpeg 没有生成有效 MP4")


def _archive_recording(session_id: str, state: RecordingTaskState) -> None:
    if not state.output_path or not state.output_url:
        return
    save_capture_archive(
        CaptureArchiveItem(
            id=f"arch-rec-{session_id}-{state.output_path.stem}",
            session_id=session_id,
            artifact_type="video",
            source="browser-video-native-playback-audio",
            path=state.output_url,
            content="",
            metadata={
                "format": "mp4",
                "audio": "playback",
                "audio_chunks": state.audio_chunks,
                "audio_bytes": state.audio_bytes,
                "video_path": str(state.video_path or ""),
                "audio_path": str(state.audio_path),
            },
        )
    )


def _recording_dir(session_id: str) -> Path:
    upload_dir = WORKSPACE_DIR / "uploads" / "recordings" / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _public_recording_url(session_id: str, output_path: Path) -> str:
    return f"/uploads/recordings/{session_id}/{output_path.name}"


def _safe_video_name(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".webm", ".mp4", ".mkv"}:
        suffix = ".webm"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return f"recording-video-{stamp}{suffix}"


def _consumer_id(session_id: str) -> str:
    return f"recorder:{session_id}"
