import asyncio
import os
import shutil
import sys
from dataclasses import dataclass
from typing import Any

from app.state import app_state

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


@dataclass(frozen=True)
class ScrcpyLaunch:
    command: list[str]
    cwd: str | None
    mode: str


scrcpy_tasks: dict[str, ScrcpyTaskState] = {}
scrcpy_clients: dict[str, list[Any]] = {}


if sys.platform == "win32":
    _QTSCRCPY_CANDIDATES = [
        r"D:\JLAO\QtScrcpy-dev\output\x64\Release\QtScrcpy.exe",
    ]
    _SCRCPY_CANDIDATES = [
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


def _find_existing(candidates: list[str]) -> str | None:
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def _get_scrcpy_exe() -> str | None:
    return _find_existing(_SCRCPY_CANDIDATES) or shutil.which("scrcpy")


def _get_qtscrcpy_exe() -> str | None:
    return _find_existing(_QTSCRCPY_CANDIDATES)


def _format_bit_rate(bit_rate: int) -> str:
    if bit_rate >= 1_000_000 and bit_rate % 1_000_000 == 0:
        return f"{bit_rate // 1_000_000}M"
    if bit_rate >= 1_000 and bit_rate % 1_000 == 0:
        return f"{bit_rate // 1_000}K"
    return str(bit_rate)


def _build_scrcpy_command(
    serial: str,
    max_size: int,
    bit_rate: int,
) -> ScrcpyLaunch:
    qtscrcpy_exe = _get_qtscrcpy_exe()
    if qtscrcpy_exe:
        return ScrcpyLaunch(
            command=[qtscrcpy_exe, "--jlao-usb-connect"],
            cwd=os.path.dirname(qtscrcpy_exe),
            mode="qtscrcpy",
        )

    scrcpy_exe = _get_scrcpy_exe()
    if not scrcpy_exe:
        raise FileNotFoundError("未找到 scrcpy.exe 或 QtScrcpy.exe，请安装命令行 scrcpy，或保留仓库内 QtScrcpy。")

    command = [scrcpy_exe]
    cleaned_serial = serial.strip()
    if cleaned_serial:
        command.extend(["-s", cleaned_serial])

    if max_size > 0:
        command.extend(["-m", str(max_size)])
    if bit_rate > 0:
        command.extend(["-b", _format_bit_rate(bit_rate)])

    command.extend(["--window-title", f"JLAO 投屏 - {cleaned_serial or '默认设备'}"])
    return ScrcpyLaunch(command=command, cwd=None, mode="scrcpy")


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
    max_size: int = 1080,
    bit_rate: int = 4_000_000,
) -> dict[str, Any]:
    if session_id not in app_state.sessions:
        raise ValueError("直播会话不存在")

    await stop_scrcpy(session_id)

    launch = _build_scrcpy_command(serial, max_size, bit_rate)
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
        max_size=max_size,
        bit_rate=bit_rate,
        process=proc,
        task=task,
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
        return {"running": False, "serial": "", "last_error": "", "width": 0, "height": 0}
    return {
        "running": task_state.running and task_state.process.returncode is None,
        "serial": task_state.serial,
        "last_error": task_state.last_error,
        "width": task_state.width,
        "height": task_state.height,
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
