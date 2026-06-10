import asyncio
import audioop
import logging
import os
import sys
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.local_stt_service import LocalChunkStt, LocalSttNotConfigured
from app.services.scrcpy_service import _get_scrcpy_exe
from app.services.transcript_service import append_transcript
from app.state import WORKSPACE_DIR, app_state
from app.ws.manager import manager

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

logger = logging.getLogger(__name__)

_NATIVE_STT_PROVIDER = "local"
_NATIVE_STT_AUDIO_SOURCE = os.getenv("NATIVE_STT_AUDIO_SOURCE", "playback").lower()


@dataclass
class NativeSttTaskState:
    session_id: str
    serial: str
    chunk_seconds: int
    task: asyncio.Task[None]
    running: bool = True
    provider: str = _NATIVE_STT_PROVIDER
    last_error: str = ""
    audio_chunks: int = 0
    audio_bytes: int = 0
    transcript_segments: int = 0


_STREAM_READ_INTERVAL_SECONDS = 0.08
_STREAM_HEADER_TIMEOUT_SECONDS = 8.0
_ADB_RECONNECT_TIMEOUT_SECONDS = 30.0
_AUDIO_RESTART_DELAY_SECONDS = 1.0
native_stt_tasks: dict[str, NativeSttTaskState] = {}
_DEFAULT_NATIVE_STT_DEVICE_KEY = "__default__"


def _create_native_stt(on_partial, on_final, on_error):
    return LocalChunkStt(on_partial=on_partial, on_final=on_final, on_error=on_error)


async def initialize_native_stt_runtime() -> None:
    native_stt_tasks.clear()
    scrcpy_exe = _get_scrcpy_exe()
    if not scrcpy_exe:
        return
    await _close_stale_native_audio_processes()
    await _recover_adb_device(serial="", scrcpy_exe=scrcpy_exe, wait_for_device=False)


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

    cleaned_serial = serial.strip()
    await _stop_native_stt_tasks_for_device(cleaned_serial, except_session_id=session_id)
    await stop_native_stt(session_id)
    task = asyncio.create_task(_native_stt_loop(session_id, cleaned_serial, chunk_seconds))
    native_stt_tasks[session_id] = NativeSttTaskState(
        session_id=session_id,
        serial=cleaned_serial,
        chunk_seconds=chunk_seconds,
        task=task,
    )
    return status(session_id)


async def stop_native_stt(session_id: str) -> dict[str, Any]:
    task_state = native_stt_tasks.get(session_id)
    if task_state:
        task_state.running = False
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
            "serial": "",
            "provider": _NATIVE_STT_PROVIDER,
            "last_error": "",
            "audio_chunks": 0,
            "audio_bytes": 0,
            "transcript_segments": 0,
        }
    return {
        "running": task_state.running and not task_state.task.done(),
        "serial": task_state.serial,
        "provider": task_state.provider,
        "last_error": task_state.last_error,
        "audio_chunks": task_state.audio_chunks,
        "audio_bytes": task_state.audio_bytes,
        "transcript_segments": task_state.transcript_segments,
    }


async def _native_stt_loop(session_id: str, serial: str, chunk_seconds: int) -> None:
    task_state = native_stt_tasks[session_id]
    chunk_dir = WORKSPACE_DIR / "tmp" / "native-stt" / session_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    wav_path: Path | None = None
    process: asyncio.subprocess.Process | None = None
    stderr_messages: list[str] = []
    stderr_task: asyncio.Task[None] | None = None

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

    stt = _create_native_stt(on_partial=on_partial, on_final=on_final, on_error=on_error)
    try:
        await stt.connect()
        task_state.last_error = ""
        logger.info("[native-stt %s] STT connected provider=%s", session_id, task_state.provider)
        await manager.broadcast(session_id, "stt_status", {"status": "connected", "provider": task_state.provider, "source": "native-scrcpy"})
        await manager.broadcast(session_id, "native_stt_status", status(session_id))

        scrcpy_exe = _get_scrcpy_exe()
        if not scrcpy_exe:
            raise FileNotFoundError("未找到 scrcpy.exe，无法采集手机原生音频。")

        while task_state.running:
            wav_path = chunk_dir / f"stream-{time.time_ns()}.wav"
            stderr_messages = []
            logger.info(
                "[native-stt %s] starting scrcpy audio capture: source=%s serial=%s path=%s",
                session_id,
                _NATIVE_STT_AUDIO_SOURCE,
                serial or "(default)",
                wav_path,
            )
            process = await _start_audio_record_process(serial=serial, output_path=wav_path, scrcpy_exe=scrcpy_exe)
            stderr_task = asyncio.create_task(_collect_process_stderr(process, stderr_messages))
            try:
                await _stream_recorded_wav(
                    process=process,
                    wav_path=wav_path,
                    stt=stt,
                    task_state=task_state,
                    stderr_messages=stderr_messages,
                )
                break
            except Exception as exc:
                if not task_state.running or not _is_scrcpy_recoverable_error(str(exc)):
                    raise
                task_state.last_error = "手机音频连接断开，正在自动重连..."
                await manager.broadcast(session_id, "stt_error", {"message": task_state.last_error})
                await manager.broadcast(session_id, "native_stt_status", status(session_id))
                await _terminate_process(process)
                process = None
                if stderr_task and not stderr_task.done():
                    stderr_task.cancel()
                stderr_task = None
                try:
                    wav_path.unlink(missing_ok=True)
                except OSError:
                    pass
                await _recover_adb_device(serial=serial, scrcpy_exe=scrcpy_exe, wait_for_device=True)
                task_state.last_error = ""
                await manager.broadcast(session_id, "native_stt_status", status(session_id))
                await asyncio.sleep(_AUDIO_RESTART_DELAY_SECONDS)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        task_state.running = False
        message = _native_stt_error_message(str(exc))
        task_state.last_error = message
        await manager.broadcast(session_id, "stt_error", {"message": message})
        await manager.broadcast(session_id, "native_stt_status", status(session_id))
    finally:
        task_state.running = False
        if process:
            await _terminate_process(process)
        if stderr_task and not stderr_task.done():
            stderr_task.cancel()
        await stt.close()
        if wav_path:
            try:
                wav_path.unlink(missing_ok=True)
            except OSError:
                pass
        await manager.broadcast(session_id, "stt_status", {"status": "closed", "provider": task_state.provider, "source": "native-scrcpy"})


async def _start_audio_record_process(serial: str, output_path: Path, scrcpy_exe: str | None = None) -> asyncio.subprocess.Process:
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


async def _stream_recorded_wav(
    process: asyncio.subprocess.Process,
    wav_path: Path,
    stt: LocalChunkStt,
    task_state: NativeSttTaskState,
    stderr_messages: list[str],
) -> None:
    channels, sample_width, sample_rate, data_offset = await _wait_for_wav_stream_header(process, wav_path, stderr_messages)
    logger.info(
        "[native-stt %s] wav header ready: channels=%d sample_width=%d sample_rate=%d data_offset=%d",
        task_state.session_id,
        channels,
        sample_width,
        sample_rate,
        data_offset,
    )
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
        task_state.last_error = ""
        log_counter += 1
        if log_counter == 1 or log_counter % 25 == 0:
            logger.info(
                "[native-stt %s] streaming audio chunks=%d bytes=%d pending=%d",
                task_state.session_id,
                task_state.audio_chunks,
                task_state.audio_bytes,
                len(pending),
            )
        await _send_pcm_frames(stt, pcm)
        await manager.broadcast(task_state.session_id, "native_stt_status", status(task_state.session_id))


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


async def _terminate_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
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


_PLAYBACK_AUDIO_UNAVAILABLE_MESSAGE = "设备当前没有可采集的手机原生音频。"


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


def _native_stt_error_message(message: str) -> str:
    if _is_playback_audio_unavailable_error(message):
        return _PLAYBACK_AUDIO_UNAVAILABLE_MESSAGE
    return f"原生手机音频转写失败：{message}"


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
        f"--audio-source={_NATIVE_STT_AUDIO_SOURCE}",
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


# 20ms PCM16 mono 16k frames keep streaming latency low.
_LOCAL_STT_FRAME_SIZE = 640


async def _send_pcm_frames(stt: LocalChunkStt, pcm: bytes) -> None:
    frame_size = _LOCAL_STT_FRAME_SIZE
    for offset in range(0, len(pcm), frame_size):
        await stt.send_audio(pcm[offset : offset + frame_size])


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

