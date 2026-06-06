import asyncio
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.repositories import save_capture_archive
from app.schemas import CaptureArchiveItem
from app.state import WORKSPACE_DIR, app_state

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@dataclass
class ScrcpyTaskState:
    session_id: str
    serial: str
    max_size: int
    bit_rate: int
    process: asyncio.subprocess.Process
    task: asyncio.Task[None]
    running: bool = True
    last_error: str = ""
    width: int = 0
    height: int = 0
    recording_path: str = ""


@dataclass(frozen=True)
class ScrcpyLaunch:
    command: list[str]
    cwd: str | None
    mode: str


scrcpy_tasks: dict[str, ScrcpyTaskState] = {}
scrcpy_clients: dict[str, list[Any]] = {}
SCRCPY_MAX_SIZE = 0  # 0 表示不限制，保持原始分辨率
WINDOWS_DRIVER_ROOT = "D:\\"


if sys.platform == "win32":
    _QTSCRCPY_CANDIDATES = [
        r"D:\JLAO\QtScrcpy-dev\output\x64\Release\QtScrcpy.exe",
        r"D:\QtScrcpy-win-x64-v3.3.3\QtScrcpy.exe",
        r"D:\QtScrcpy-win-x64-v3.3.3",
    ]
    _SCRCPY_CANDIDATES = [
        r"D:\scrcpy-win64-v4.0\scrcpy.exe",
        r"D:\scrcpy\scrcpy.exe",
        r"D:\scrcpy-win64-v3.3.4\scrcpy.exe",
        r"C:\Program Files\scrcpy\scrcpy.exe",
        r"C:\ProgramData\chocolatey\bin\scrcpy.exe",
        r"C:\Users\Administrator\scoop\shims\scrcpy.exe",
    ]
else:
    _QTSCRCPY_CANDIDATES: list[str] = []
    _SCRCPY_CANDIDATES = [
        "/usr/bin/scrcpy",
        "/usr/local/bin/scrcpy",
        "/opt/scrcpy/scrcpy",
    ]

# 用户手动指定的 scrcpy 路径（优先级最高）
_user_scrcpy_path: str | None = None


def _normalize_user_scrcpy_path(path: str) -> str:
    cleaned = path.strip().strip('"')
    if not cleaned:
        raise FileNotFoundError("scrcpy 驱动路径不能为空")

    if os.path.isdir(cleaned):
        for exe_name in ("scrcpy.exe", "QtScrcpy.exe"):
            exe_path = os.path.join(cleaned, exe_name)
            if os.path.isfile(exe_path):
                return exe_path
        raise FileNotFoundError(f"目录中未找到 QtScrcpy.exe 或 scrcpy.exe：{cleaned}")

    if not os.path.isfile(cleaned):
        raise FileNotFoundError(f"scrcpy 驱动路径不存在：{cleaned}")

    return cleaned


def _scrcpy_driver_type(path: str) -> str:
    basename = os.path.basename(path).lower()
    return "qtscrcpy" if basename == "qtscrcpy.exe" else "scrcpy"


def set_scrcpy_path(path: str | None) -> str | None:
    """设置用户指定的 scrcpy 路径。"""
    global _user_scrcpy_path
    _user_scrcpy_path = _normalize_user_scrcpy_path(path) if path else None
    return _user_scrcpy_path


def get_available_drivers() -> list[dict[str, str]]:
    """获取所有可用的 scrcpy 驱动列表。"""
    drivers = []

    seen_paths: set[str] = set()

    def add_driver(name: str, path: str, driver_type: str) -> None:
        normalized_path = _normalize_user_scrcpy_path(path)
        if normalized_path in seen_paths:
            return
        seen_paths.add(normalized_path)
        drivers.append({
            "name": name,
            "path": normalized_path,
            "type": driver_type,
        })

    for candidate in _SCRCPY_CANDIDATES:
        if os.path.exists(candidate):
            add_driver("命令行 scrcpy", candidate, "scrcpy")

    scrcpy_in_path = shutil.which("scrcpy")
    if scrcpy_in_path and not any(d["path"] == scrcpy_in_path for d in drivers):
        add_driver("命令行 scrcpy (PATH)", scrcpy_in_path, "scrcpy")

    for candidate in _QTSCRCPY_CANDIDATES:
        if os.path.exists(candidate):
            add_driver("QtScrcpy", candidate, "qtscrcpy")

    # 检查用户指定的路径
    if _user_scrcpy_path:
        driver_type = _scrcpy_driver_type(_user_scrcpy_path)
        drivers.insert(0, {
            "name": "用户指定" + (" (QtScrcpy)" if driver_type == "qtscrcpy" else " (scrcpy)"),
            "path": _user_scrcpy_path,
            "type": driver_type,
        })

    return drivers


def _find_existing(candidates: list[str]) -> str | None:
    for candidate in candidates:
        if not os.path.exists(candidate):
            continue
        try:
            return _normalize_user_scrcpy_path(candidate)
        except FileNotFoundError:
            continue
    return None


def _get_scrcpy_exe() -> str | None:
    # 优先使用用户指定的路径
    if _user_scrcpy_path and _scrcpy_driver_type(_user_scrcpy_path) == "scrcpy":
        return _user_scrcpy_path
    return _find_existing(_SCRCPY_CANDIDATES) or shutil.which("scrcpy")


def _get_qtscrcpy_exe() -> str | None:
    # 优先使用用户指定的路径（如果是 QtScrcpy）
    if _user_scrcpy_path and _scrcpy_driver_type(_user_scrcpy_path) == "qtscrcpy":
        return _user_scrcpy_path
    return _find_existing(_QTSCRCPY_CANDIDATES)


def _format_bit_rate(bit_rate: int) -> str:
    if bit_rate >= 1_000_000 and bit_rate % 1_000_000 == 0:
        return f"{bit_rate // 1_000_000}M"
    if bit_rate >= 1_000 and bit_rate % 1_000 == 0:
        return f"{bit_rate // 1_000}K"
    return str(bit_rate)


def _build_qtscrcpy_launch(qtscrcpy_exe: str) -> ScrcpyLaunch:
    return ScrcpyLaunch(
        command=[qtscrcpy_exe, "--jlao-usb-connect"],
        cwd=os.path.dirname(qtscrcpy_exe),
        mode="qtscrcpy",
    )


def _build_scrcpy_command(
    serial: str,
    max_size: int,
    bit_rate: int,
    record_path: Path | None = None,
) -> ScrcpyLaunch:
    if _user_scrcpy_path and _scrcpy_driver_type(_user_scrcpy_path) == "qtscrcpy":
        return _build_qtscrcpy_launch(_user_scrcpy_path)

    scrcpy_exe = _get_scrcpy_exe()
    if not scrcpy_exe:
        qtscrcpy_exe = _get_qtscrcpy_exe()
        if qtscrcpy_exe:
            return _build_qtscrcpy_launch(qtscrcpy_exe)
        raise FileNotFoundError("未找到 scrcpy.exe 或 QtScrcpy.exe，请安装命令行 scrcpy，或保留仓库内 QtScrcpy。")

    command = [scrcpy_exe]
    cleaned_serial = serial.strip()
    if cleaned_serial:
        command.extend(["-s", cleaned_serial])

    effective_max_size = SCRCPY_MAX_SIZE
    if effective_max_size > 0:
        command.extend(["-m", str(effective_max_size)])
    if bit_rate > 0:
        command.extend(["-b", _format_bit_rate(bit_rate)])

    command.append("--audio-source=playback")
    if record_path:
        command.extend(["--record", str(record_path), "--record-format", "mp4"])
    command.extend(["--window-title", f"JLAO 投屏 - {cleaned_serial or '默认设备'}"])
    return ScrcpyLaunch(command=command, cwd=None, mode="scrcpy")

def _new_recording_path(session_id: str) -> tuple[Path, str]:
    upload_dir = WORKSPACE_DIR / "uploads" / "recordings" / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    record_path = upload_dir / f"screen-{stamp}.mp4"
    record_url = f"/uploads/recordings/{session_id}/{record_path.name}"
    return record_path, record_url


async def _read_stderr(proc: asyncio.subprocess.Process, session_id: str) -> str:
    messages: list[str] = []
    if not proc.stderr:
        return ""

    while True:
        line = await proc.stderr.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="ignore").strip()
        if text:
            messages.append(text)
            print(f"[scrcpy {session_id}] {text}")

            task_state = scrcpy_tasks.get(session_id)
            if task_state and ("ERROR" in text.upper() or "FAILED" in text.upper()):
                task_state.last_error = text

    return "\n".join(messages[-10:])


async def _scrcpy_monitor(session_id: str, proc: asyncio.subprocess.Process) -> None:
    stderr_task = asyncio.create_task(_read_stderr(proc, session_id))
    try:
        return_code = await proc.wait()
        stderr_text = await stderr_task
        task_state = scrcpy_tasks.get(session_id)
        if not task_state:
            return

        task_state.running = False
        if return_code != 0:
            task_state.last_error = stderr_text or f"scrcpy 已退出，退出码：{return_code}"
        elif not task_state.last_error:
            task_state.last_error = "scrcpy 窗口已关闭"
    except asyncio.CancelledError:
        stderr_task.cancel()
        raise


async def _terminate_process(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=3.0)
    except Exception:
        try:
            proc.kill()
            await asyncio.wait_for(proc.wait(), timeout=3.0)
        except Exception:
            pass


async def start_scrcpy(
    session_id: str,
    serial: str,
    max_size: int = SCRCPY_MAX_SIZE,
    bit_rate: int = 4_000_000,
) -> dict[str, Any]:
    if session_id not in app_state.sessions:
        raise ValueError("直播会话不存在")

    await stop_scrcpy(session_id)

    effective_max_size = SCRCPY_MAX_SIZE
    record_path, record_url = _new_recording_path(session_id)
    launch = _build_scrcpy_command(serial, effective_max_size, bit_rate, record_path=record_path)
    cleaned_serial = serial.strip()
    print(f"[scrcpy {session_id}] Starting native window ({launch.mode}): {' '.join(launch.command)}")

    proc = await asyncio.create_subprocess_exec(
        *launch.command,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        cwd=launch.cwd,
    )

    task = asyncio.create_task(_scrcpy_monitor(session_id, proc))
    scrcpy_tasks[session_id] = ScrcpyTaskState(
        session_id=session_id,
        serial=cleaned_serial,
        max_size=effective_max_size,
        bit_rate=bit_rate,
        process=proc,
        task=task,
        recording_path=record_url if launch.mode == "scrcpy" else "",
    )

    await asyncio.sleep(0.8)
    if proc.returncode is not None:
        try:
            await task
        except asyncio.CancelledError:
            pass
        current = status(session_id)
        scrcpy_tasks.pop(session_id, None)
        return current

    if launch.mode == "scrcpy":
        save_capture_archive(
            CaptureArchiveItem(
                id=f"arch-rec-{session_id}-{record_path.stem}",
                session_id=session_id,
                artifact_type="video",
                source="scrcpy-record",
                path=record_url,
                content="",
                metadata={
                    "serial": cleaned_serial,
                    "max_size": effective_max_size,
                    "bit_rate": bit_rate,
                    "format": "mp4",
                    "audio": "playback",
                },
            )
        )

    return status(session_id)


async def stop_scrcpy(session_id: str) -> dict[str, Any]:
    task_state = scrcpy_tasks.get(session_id)
    if task_state:
        task_state.running = False
        await _terminate_process(task_state.process)
        if not task_state.task.done():
            task_state.task.cancel()
            try:
                await task_state.task
            except asyncio.CancelledError:
                pass
        scrcpy_tasks.pop(session_id, None)
        scrcpy_clients.pop(session_id, None)
    return status(session_id)


def status(session_id: str) -> dict[str, Any]:
    task_state = scrcpy_tasks.get(session_id)
    if not task_state:
        return {"running": False, "serial": "", "last_error": "", "width": 0, "height": 0, "recording_path": ""}
    return {
        "running": task_state.running and task_state.process.returncode is None,
        "serial": task_state.serial,
        "last_error": task_state.last_error,
        "width": task_state.width,
        "height": task_state.height,
        "recording_path": task_state.recording_path,
    }


def add_client(session_id: str, websocket: Any) -> None:
    if session_id not in scrcpy_clients:
        scrcpy_clients[session_id] = []
    scrcpy_clients[session_id].append(websocket)


def remove_client(session_id: str, websocket: Any) -> None:
    clients = scrcpy_clients.get(session_id, [])
    try:
        clients.remove(websocket)
    except ValueError:
        pass
    if not clients:
        scrcpy_clients.pop(session_id, None)
