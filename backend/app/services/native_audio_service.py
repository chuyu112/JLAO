from __future__ import annotations

import asyncio
import audioop
import logging
import os
import sys
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.services.scrcpy_service import _get_scrcpy_exe
from app.state import WORKSPACE_DIR, app_state
from app.ws.manager import manager

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

logger = logging.getLogger(__name__)

NativeAudioFrameCallback = Callable[[bytes], Awaitable[None]]

_NATIVE_AUDIO_SOURCE = os.getenv("NATIVE_STT_AUDIO_SOURCE", os.getenv("NATIVE_AUDIO_SOURCE", "playback")).lower()
_STREAM_READ_INTERVAL_SECONDS = 0.08
_STREAM_HEADER_TIMEOUT_SECONDS = 8.0
_ADB_RECONNECT_TIMEOUT_SECONDS = 30.0
_AUDIO_RESTART_DELAY_SECONDS = 1.0
_MAX_AUTO_RECONNECT_ATTEMPTS = 1
_DEFAULT_DEVICE_KEY = "__default__"
_PLAYBACK_AUDIO_UNAVAILABLE_MESSAGE = "设备当前没有可采集的手机原生音频。"


@dataclass
class NativeAudioStreamState:
    session_id: str
    serial: str
    task: asyncio.Task[None]
    process: asyncio.subprocess.Process | None = None
    source: str = _NATIVE_AUDIO_SOURCE
    device_id: str = ""
    device_name: str = ""
    running: bool = True
    resource_state: str = "starting"
    last_error: str = ""
    reconnecting: bool = False
    reconnect_attempts: int = 0
    audio_chunks: int = 0
    audio_bytes: int = 0
    current_wav_path: str = ""
    subscribers: dict[str, NativeAudioFrameCallback] = field(default_factory=dict)


native_audio_streams: dict[str, NativeAudioStreamState] = {}


async def initialize_native_audio_runtime() -> None:
    native_audio_streams.clear()
    scrcpy_exe = _get_scrcpy_exe()
    if not scrcpy_exe:
        return
    await cleanup_stale_native_audio_processes()
    await _recover_adb_device(serial="", scrcpy_exe=scrcpy_exe, wait_for_device=False)


async def cleanup_stale_native_audio_processes() -> None:
    await _close_stale_native_audio_processes()


async def recover_adb_once(serial: str = "") -> None:
    scrcpy_exe = _get_scrcpy_exe()
    if not scrcpy_exe:
        return
    await _recover_adb_device(serial=serial, scrcpy_exe=scrcpy_exe, wait_for_device=False)


async def get_adb_devices_status() -> dict[str, Any]:
    scrcpy_exe = _get_scrcpy_exe()
    if not scrcpy_exe:
        return {
            "status": "unknown",
            "available": False,
            "adb_path": "",
            "devices": [],
            "device_count": 0,
            "online_count": 0,
            "offline_count": 0,
            "error": "未找到 scrcpy.exe，无法定位 adb。",
        }

    adb_exe = _adb_exe_for_scrcpy(scrcpy_exe)
    command = [adb_exe, "devices"]
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5.0)
    except asyncio.TimeoutError:
        return {
            "status": "timeout",
            "available": False,
            "adb_path": adb_exe,
            "devices": [],
            "device_count": 0,
            "online_count": 0,
            "offline_count": 0,
            "error": "读取 adb devices 超时。",
        }
    except Exception as exc:
        return {
            "status": "error",
            "available": False,
            "adb_path": adb_exe,
            "devices": [],
            "device_count": 0,
            "online_count": 0,
            "offline_count": 0,
            "error": str(exc),
        }

    text = (stdout or b"").decode("utf-8", errors="ignore")
    error = (stderr or b"").decode("utf-8", errors="ignore").strip()
    devices = _parse_adb_devices_output(text)
    online_count = sum(1 for item in devices if item["state"] == "device")
    offline_count = sum(1 for item in devices if item["state"] == "offline")
    if process.returncode != 0:
        status_value = "error"
    elif online_count:
        status_value = "online"
    elif offline_count:
        status_value = "offline"
    else:
        status_value = "none"
    return {
        "status": status_value,
        "available": process.returncode == 0 and online_count > 0,
        "adb_path": adb_exe,
        "devices": devices,
        "device_count": len(devices),
        "online_count": online_count,
        "offline_count": offline_count,
        "error": error if process.returncode != 0 else "",
    }


async def start_native_audio(
    session_id: str,
    serial: str = "",
    *,
    source: str = "",
    device_id: str = "",
    device_name: str = "",
) -> dict[str, Any]:
    if session_id not in app_state.sessions:
        raise ValueError("直播会话不存在")

    await stop_native_audio(session_id, force=True)
    cleaned_serial = serial.strip()
    normalized_source = _normalize_audio_source(source)
    task = asyncio.create_task(_native_audio_loop(session_id, cleaned_serial))
    native_audio_streams[session_id] = NativeAudioStreamState(
        session_id=session_id,
        serial=cleaned_serial,
        task=task,
        source=normalized_source,
        device_id=device_id.strip(),
        device_name=device_name.strip(),
    )
    logger.info(
        "[native-audio %s] starting source=%s serial=%s device_id=%s device_name=%s",
        session_id,
        normalized_source,
        cleaned_serial or "(default)",
        device_id or "(auto)",
        device_name or "(auto)",
    )
    await manager.broadcast(session_id, "native_audio_status", status(session_id))
    return status(session_id)


async def stop_native_audio(session_id: str, *, force: bool = False) -> dict[str, Any]:
    task_state = native_audio_streams.get(session_id)
    if not task_state:
        return status(session_id)
    if task_state.subscribers and not force:
        consumers = ", ".join(sorted(task_state.subscribers))
        raise RuntimeError(f"音频接入正在被使用，请先停止：{consumers}")

    logger.info("[native-audio %s] stopping force=%s", session_id, force)
    task_state.running = False
    task_state.resource_state = "stopping"
    await _terminate_process(task_state.process)
    if task_state.task and not task_state.task.done():
        task_state.task.cancel()
        try:
            await task_state.task
        except asyncio.CancelledError:
            pass
    native_audio_streams.pop(session_id, None)
    await manager.broadcast(session_id, "native_audio_status", status(session_id))
    return status(session_id)


def status(session_id: str) -> dict[str, Any]:
    task_state = native_audio_streams.get(session_id)
    if not task_state:
        return {
            "running": False,
            "state": "stopped",
            "serial": "",
            "source": _NATIVE_AUDIO_SOURCE,
            "device_id": "",
            "device_name": "",
            "last_error": "",
            "audio_chunks": 0,
            "audio_bytes": 0,
            "reconnecting": False,
            "reconnect_attempts": 0,
            "consumers": [],
        }
    task_running = task_state.running and not task_state.task.done()
    return {
        "running": task_running and task_state.resource_state == "running",
        "state": task_state.resource_state if task_running or task_state.resource_state == "error" else "stopped",
        "serial": task_state.serial,
        "source": task_state.source,
        "device_id": task_state.device_id,
        "device_name": task_state.device_name,
        "last_error": task_state.last_error,
        "audio_chunks": task_state.audio_chunks,
        "audio_bytes": task_state.audio_bytes,
        "reconnecting": task_state.reconnecting,
        "reconnect_attempts": task_state.reconnect_attempts,
        "consumers": sorted(task_state.subscribers),
    }


def is_running(session_id: str) -> bool:
    info = status(session_id)
    return bool(info["running"])


def subscribe_audio_frames(session_id: str, consumer_id: str, callback: NativeAudioFrameCallback) -> None:
    task_state = native_audio_streams.get(session_id)
    if not task_state or not task_state.running:
        raise RuntimeError("请先打开音频接入")
    task_state.subscribers[consumer_id] = callback
    logger.info("[native-audio %s] subscriber added: %s", session_id, consumer_id)


def unsubscribe_audio_frames(session_id: str, consumer_id: str) -> None:
    task_state = native_audio_streams.get(session_id)
    if not task_state:
        return
    task_state.subscribers.pop(consumer_id, None)
    logger.info("[native-audio %s] subscriber removed: %s", session_id, consumer_id)


async def _native_audio_loop(session_id: str, serial: str) -> None:
    task_state = native_audio_streams[session_id]
    if task_state.source == "capture_card":
        await _capture_card_audio_loop(task_state)
        return

    chunk_dir = WORKSPACE_DIR / "tmp" / "native-audio" / session_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    scrcpy_exe = _get_scrcpy_exe()
    if not scrcpy_exe:
        task_state.running = False
        task_state.resource_state = "error"
        task_state.last_error = "未找到 scrcpy.exe，无法采集手机原生音频。"
        await manager.broadcast(session_id, "native_audio_status", status(session_id))
        return

    process: asyncio.subprocess.Process | None = None
    stderr_task: asyncio.Task[None] | None = None
    wav_path: Path | None = None
    try:
        while task_state.running:
            stderr_messages: list[str] = []
            wav_path = chunk_dir / f"stream-{time.time_ns()}.wav"
            task_state.current_wav_path = str(wav_path)
            task_state.resource_state = "starting"
            task_state.last_error = ""
            await manager.broadcast(session_id, "native_audio_status", status(session_id))

            logger.info(
                "[native-audio %s] starting scrcpy audio capture: source=%s serial=%s path=%s",
                session_id,
                _NATIVE_AUDIO_SOURCE,
                serial or "(default)",
                wav_path,
            )
            process = await _start_audio_record_process(serial=serial, output_path=wav_path, scrcpy_exe=scrcpy_exe)
            task_state.process = process
            stderr_task = asyncio.create_task(_collect_process_stderr(process, stderr_messages))
            try:
                await _stream_recorded_wav(process, wav_path, task_state, stderr_messages)
                if task_state.running:
                    raise RuntimeError(_scrcpy_error_message(process.returncode or 0, stderr_messages) or "手机音频流已断开")
                break
            except Exception as exc:
                message = _native_audio_error_message(str(exc))
                if (
                    task_state.running
                    and _is_scrcpy_recoverable_error(str(exc))
                    and task_state.reconnect_attempts < _MAX_AUTO_RECONNECT_ATTEMPTS
                ):
                    task_state.reconnect_attempts += 1
                    task_state.reconnecting = True
                    task_state.resource_state = "starting"
                    task_state.last_error = "手机音频连接断开，正在自动重连一次..."
                    logger.warning("[native-audio %s] reconnecting after error: %s", session_id, exc)
                    await manager.broadcast(session_id, "native_audio_status", status(session_id))
                    await _terminate_process(process)
                    process = None
                    if stderr_task and not stderr_task.done():
                        stderr_task.cancel()
                    stderr_task = None
                    await _recover_adb_device(serial=serial, scrcpy_exe=scrcpy_exe, wait_for_device=True)
                    task_state.reconnecting = False
                    await asyncio.sleep(_AUDIO_RESTART_DELAY_SECONDS)
                    continue

                task_state.running = False
                task_state.reconnecting = False
                task_state.resource_state = "error"
                task_state.last_error = message
                logger.error("[native-audio %s] failed: %s", session_id, message)
                await manager.broadcast(session_id, "native_audio_status", status(session_id))
                break
            finally:
                if stderr_task and not stderr_task.done():
                    stderr_task.cancel()
                stderr_task = None
                await _terminate_process(process)
                process = None
                task_state.process = None
                if wav_path:
                    try:
                        wav_path.unlink(missing_ok=True)
                    except OSError:
                        pass
    except asyncio.CancelledError:
        raise
    finally:
        task_state.running = False
        if task_state.resource_state not in {"error", "stopping"}:
            task_state.resource_state = "stopped"
        await _terminate_process(process)
        if stderr_task and not stderr_task.done():
            stderr_task.cancel()
        await manager.broadcast(session_id, "native_audio_status", status(session_id))


async def _capture_card_audio_loop(task_state: NativeAudioStreamState) -> None:
    process: asyncio.subprocess.Process | None = None
    stderr_task: asyncio.Task[None] | None = None
    stderr_messages: list[str] = []
    try:
        task_state.resource_state = "starting"
        task_state.last_error = ""
        await manager.broadcast(task_state.session_id, "native_audio_status", status(task_state.session_id))

        device_name = await _resolve_capture_card_audio_device_name(task_state.device_id, task_state.device_name)
        task_state.device_name = device_name
        ffmpeg = _get_ffmpeg_exe()
        command = _build_capture_card_audio_command(ffmpeg, device_name)
        logger.info("[native-audio %s] starting capture-card audio: %s", task_state.session_id, " ".join(command))
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        task_state.process = process
        stderr_task = asyncio.create_task(_collect_process_stderr(process, stderr_messages))
        task_state.resource_state = "running"
        task_state.last_error = ""
        await manager.broadcast(task_state.session_id, "native_audio_status", status(task_state.session_id))

        chunk_size = int(16000 * 2 * _STREAM_READ_INTERVAL_SECONDS)
        while task_state.running:
            if process.returncode is not None:
                if process.returncode != 0:
                    raise RuntimeError(_capture_card_audio_error_message(process.returncode, stderr_messages, device_name))
                break
            if not process.stdout:
                raise RuntimeError("采集卡音频进程没有输出 PCM 数据")
            try:
                pcm = await asyncio.wait_for(process.stdout.read(chunk_size), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if not pcm:
                if process.returncode is not None:
                    break
                continue
            task_state.audio_chunks += 1
            task_state.audio_bytes += len(pcm)
            await _publish_pcm(task_state, pcm)
            await manager.broadcast(task_state.session_id, "native_audio_status", status(task_state.session_id))

        if task_state.running:
            raise RuntimeError("采集卡音频流已断开")
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        task_state.running = False
        task_state.resource_state = "error"
        task_state.last_error = str(exc)
        logger.error("[native-audio %s] capture-card audio failed: %s", task_state.session_id, task_state.last_error)
        await manager.broadcast(task_state.session_id, "native_audio_status", status(task_state.session_id))
    finally:
        task_state.running = False
        if task_state.resource_state not in {"error", "stopping"}:
            task_state.resource_state = "stopped"
        await _terminate_process(process)
        task_state.process = None
        if stderr_task and not stderr_task.done():
            stderr_task.cancel()
        await manager.broadcast(task_state.session_id, "native_audio_status", status(task_state.session_id))


async def _start_audio_record_process(
    serial: str,
    output_path: Path,
    scrcpy_exe: str | None = None,
) -> asyncio.subprocess.Process:
    scrcpy_exe = scrcpy_exe or _get_scrcpy_exe()
    if not scrcpy_exe:
        raise FileNotFoundError("未找到 scrcpy.exe，无法采集手机原生音频。")

    command = _build_audio_record_command(scrcpy_exe, serial, output_path)
    return await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=os.path.dirname(scrcpy_exe),
    )


def _normalize_audio_source(source: str) -> str:
    cleaned = (source or "").strip().lower().replace("-", "_")
    if cleaned in {"capture_card", "capture-card", "hdmi"}:
        return "capture_card"
    return _NATIVE_AUDIO_SOURCE


def _get_ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


async def _resolve_capture_card_audio_device_name(device_id: str = "", device_name: str = "") -> str:
    if device_name.strip():
        return device_name.strip()

    from app.services import capture_card_service

    devices = await capture_card_service.enumerate_devices()
    audio_devices = devices.get("audio_devices") or []
    cleaned_device_id = device_id.strip()
    if cleaned_device_id:
        for device in audio_devices:
            if cleaned_device_id in {str(device.get("id") or ""), str(device.get("device_id") or "")}:
                name = str(device.get("name") or "").strip()
                if name:
                    return name

    for device in audio_devices:
        if device.get("is_capture_candidate"):
            name = str(device.get("name") or "").strip()
            if name:
                return name
    if audio_devices:
        name = str(audio_devices[0].get("name") or "").strip()
        if name:
            return name
    raise RuntimeError("未检测到可用的采集卡音频设备")


def _build_capture_card_audio_command(ffmpeg_exe: str, device_name: str) -> list[str]:
    return [
        ffmpeg_exe,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-f",
        "dshow",
        "-thread_queue_size",
        "512",
        "-rtbufsize",
        "64M",
        "-i",
        f"audio={device_name}",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-acodec",
        "pcm_s16le",
        "-f",
        "s16le",
        "pipe:1",
    ]


def _capture_card_audio_error_message(return_code: int, stderr_messages: list[str], device_name: str) -> str:
    message = "\n".join(stderr_messages).strip()
    if not message:
        message = f"ffmpeg 退出码：{return_code}"
    return f"采集卡音频接入失败（{device_name}）：{message}"


async def _stream_recorded_wav(
    process: asyncio.subprocess.Process,
    wav_path: Path,
    task_state: NativeAudioStreamState,
    stderr_messages: list[str],
) -> None:
    channels, sample_width, sample_rate, data_offset = await _wait_for_wav_stream_header(process, wav_path, stderr_messages)
    logger.info(
        "[native-audio %s] wav header ready: channels=%d sample_width=%d sample_rate=%d data_offset=%d",
        task_state.session_id,
        channels,
        sample_width,
        sample_rate,
        data_offset,
    )
    task_state.resource_state = "running"
    task_state.last_error = ""
    task_state.reconnecting = False
    await manager.broadcast(task_state.session_id, "native_audio_status", status(task_state.session_id))

    block_align = channels * sample_width
    read_offset = data_offset
    pending = b""
    rate_state: Any = None
    log_counter = 0

    while task_state.running:
        if process.returncode is not None:
            if process.returncode != 0:
                raise RuntimeError(_scrcpy_error_message(process.returncode, stderr_messages))
            break

        current_size = await asyncio.to_thread(_file_size, wav_path)
        if current_size <= read_offset:
            await asyncio.sleep(_STREAM_READ_INTERVAL_SECONDS)
            continue

        new_data = await asyncio.to_thread(_read_file_range, wav_path, read_offset, current_size - read_offset)
        read_offset += len(new_data)
        pending += new_data

        usable_size = len(pending) - (len(pending) % block_align)
        if usable_size <= 0:
            continue

        pcm, rate_state = _pcm_to_pcm16_mono_16k(
            pending[:usable_size],
            channels=channels,
            sample_width=sample_width,
            sample_rate=sample_rate,
            rate_state=rate_state,
        )
        pending = pending[usable_size:]
        if not pcm:
            continue

        task_state.audio_chunks += 1
        task_state.audio_bytes += len(pcm)
        log_counter += 1
        if log_counter == 1 or log_counter % 25 == 0:
            logger.info(
                "[native-audio %s] streaming chunks=%d bytes=%d subscribers=%d",
                task_state.session_id,
                task_state.audio_chunks,
                task_state.audio_bytes,
                len(task_state.subscribers),
            )
        await _publish_pcm(task_state, pcm)
        await manager.broadcast(task_state.session_id, "native_audio_status", status(task_state.session_id))


async def _publish_pcm(task_state: NativeAudioStreamState, pcm: bytes) -> None:
    for consumer_id, callback in list(task_state.subscribers.items()):
        try:
            await callback(pcm)
        except Exception as exc:
            logger.warning("[native-audio %s] subscriber %s failed: %s", task_state.session_id, consumer_id, exc)


async def _wait_for_wav_stream_header(
    process: asyncio.subprocess.Process,
    wav_path: Path,
    stderr_messages: list[str],
) -> tuple[int, int, int, int]:
    deadline = asyncio.get_running_loop().time() + _STREAM_HEADER_TIMEOUT_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        if process.returncode is not None:
            raise RuntimeError(_scrcpy_error_message(process.returncode, stderr_messages))
        header = await asyncio.to_thread(_read_wav_stream_header, wav_path)
        if header:
            return header
        await asyncio.sleep(_STREAM_READ_INTERVAL_SECONDS)
    raise RuntimeError("等待 scrcpy 音频流超时")


def _read_wav_stream_header(path: Path) -> tuple[int, int, int, int] | None:
    if not path.exists() or path.stat().st_size < 44:
        return None
    header = path.read_bytes()[:4096]
    data_offset = _find_wav_data_offset(header)
    if data_offset is None:
        return None
    with wave.open(str(path), "rb") as wav_file:
        return wav_file.getnchannels(), wav_file.getsampwidth(), wav_file.getframerate(), data_offset


def _find_wav_data_offset(header: bytes) -> int | None:
    if len(header) < 20 or not header.startswith(b"RIFF") or header[8:12] != b"WAVE":
        return None
    offset = 12
    while offset + 8 <= len(header):
        chunk_id = header[offset : offset + 4]
        chunk_size = int.from_bytes(header[offset + 4 : offset + 8], "little")
        data_start = offset + 8
        if chunk_id == b"data":
            return data_start
        offset = data_start + chunk_size + (chunk_size % 2)
    return None


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _read_file_range(path: Path, offset: int, size: int) -> bytes:
    with path.open("rb") as stream:
        stream.seek(offset)
        return stream.read(size)


def _pcm_to_pcm16_mono_16k(
    frames: bytes,
    channels: int,
    sample_width: int,
    sample_rate: int,
    rate_state: Any = None,
) -> tuple[bytes, Any]:
    if sample_width != 2:
        frames = audioop.lin2lin(frames, sample_width, 2)
        sample_width = 2
    if channels > 1:
        frames = audioop.tomono(frames, sample_width, 0.5, 0.5)
    if sample_rate != 16000:
        frames, rate_state = audioop.ratecv(frames, sample_width, 1, sample_rate, 16000, rate_state)
    return frames, rate_state


async def _collect_process_stderr(process: asyncio.subprocess.Process, messages: list[str]) -> None:
    if not process.stderr:
        return
    while True:
        line = await process.stderr.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="ignore").strip()
        if text:
            messages.append(text)
            del messages[:-10]
            logger.info("[native-audio stderr] %s", text)


async def _terminate_process(process: asyncio.subprocess.Process | None) -> None:
    if process is None or process.returncode is not None:
        return
    try:
        process.terminate()
        await asyncio.wait_for(process.wait(), timeout=3)
    except Exception:
        process.kill()
        await process.wait()


def _scrcpy_error_message(return_code: int, stderr_messages: list[str]) -> str:
    message = "\n".join(stderr_messages).strip()
    if _is_playback_audio_unavailable_error(message):
        return _PLAYBACK_AUDIO_UNAVAILABLE_MESSAGE
    return message or f"scrcpy 音频采集失败，退出码：{return_code}"


def _is_playback_audio_unavailable_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "stream explicitly disabled by the device" in lowered
        or "audio stream recording disabled" in lowered
        or "no streams to mux were specified" in lowered
    )


def _is_device_disconnected_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "device disconnected" in lowered
        or "device offline" in lowered
        or "\toffline" in lowered
        or ("adb: device" in lowered and "offline" in lowered)
    )


def _is_scrcpy_recoverable_error(message: str) -> bool:
    lowered = message.lower()
    return (
        _is_device_disconnected_error(message)
        or "server connection failed" in lowered
        or "connection failed" in lowered
        or "connection reset" in lowered
        or "connection closed" in lowered
        or "aborted" in lowered
    )


def _native_audio_error_message(message: str) -> str:
    if _is_playback_audio_unavailable_error(message):
        return _PLAYBACK_AUDIO_UNAVAILABLE_MESSAGE
    return f"手机音频接入失败：{message}"


async def _recover_adb_device(serial: str, scrcpy_exe: str, wait_for_device: bool = True) -> None:
    adb_exe = _adb_exe_for_scrcpy(scrcpy_exe)
    await _run_adb_command(adb_exe, serial, ["reconnect", "offline"], timeout=10.0, allow_failure=True)
    await _run_adb_command(adb_exe, serial, ["reconnect", "device"], timeout=10.0, allow_failure=True)
    if wait_for_device:
        await _run_adb_command(adb_exe, serial, ["wait-for-device"], timeout=_ADB_RECONNECT_TIMEOUT_SECONDS)


async def _close_stale_native_audio_processes() -> None:
    if sys.platform != "win32":
        return
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -ieq 'scrcpy.exe' "
        "-and $_.CommandLine -like '*--no-video*' "
        "-and $_.CommandLine -like '*--record-format*wav*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        process = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NoProfile",
            "-Command",
            script,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(process.wait(), timeout=5.0)
    except Exception:
        return


def _adb_exe_for_scrcpy(scrcpy_exe: str) -> str:
    candidate = Path(scrcpy_exe).with_name("adb.exe" if sys.platform == "win32" else "adb")
    if candidate.exists():
        return str(candidate)
    return "adb"


def _parse_adb_devices_output(text: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("list of devices"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        devices.append({"serial": parts[0], "state": parts[1], "raw": line})
    return devices


async def _run_adb_command(
    adb_exe: str,
    serial: str,
    args: list[str],
    timeout: float,
    allow_failure: bool = False,
) -> None:
    command = [adb_exe]
    if serial:
        command.extend(["-s", serial])
    command.extend(args)
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.wait()
        raise RuntimeError("等待手机 ADB 自动重连超时") from exc
    if process.returncode != 0 and not allow_failure:
        message = (stderr or stdout).decode("utf-8", errors="ignore").strip()
        raise RuntimeError(message or f"ADB 自动重连失败，退出码：{process.returncode}")


def _build_audio_record_command(scrcpy_exe: str, serial: str, output_path: Path, chunk_seconds: int = 0) -> list[str]:
    command = [
        scrcpy_exe,
        "--no-video",
        "--no-window",
        "--no-audio-playback",
        f"--audio-source={_NATIVE_AUDIO_SOURCE}",
        "--audio-codec=raw",
        "--record",
        str(output_path),
        "--record-format",
        "wav",
        "--require-audio",
    ]
    if serial:
        command[1:1] = ["-s", serial]
    return command


def _device_key(serial: str) -> str:
    return serial.strip() or _DEFAULT_DEVICE_KEY


def _sessions_for_native_audio_device(serial: str) -> list[str]:
    key = _device_key(serial)
    return [
        session_id
        for session_id, task_state in native_audio_streams.items()
        if _device_key(task_state.serial) == key
    ]


def _wav_to_pcm16_mono_16k(path: str) -> bytes:
    with wave.open(path, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())

    if sample_width != 2:
        frames = audioop.lin2lin(frames, sample_width, 2)
        sample_width = 2
    if channels > 1:
        frames = audioop.tomono(frames, sample_width, 0.5, 0.5)
    if sample_rate != 16000:
        frames, _ = audioop.ratecv(frames, sample_width, 1, sample_rate, 16000, None)
    return frames
