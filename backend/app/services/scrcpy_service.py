import asyncio
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
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
    process: asyncio.subprocess.Process | None = None
    task: asyncio.Task[None] | None = None
    running: bool = True
    reconnecting: bool = False
    reconnect_attempts: int = 0
    last_exit_code: int | None = None
    last_error: str = ""
    width: int = 0
    height: int = 0
    recording_path: str = ""
    mode: str = ""


@dataclass(frozen=True)
class ScrcpyLaunch:
    command: list[str]
    cwd: str | None
    mode: str


scrcpy_tasks: dict[str, ScrcpyTaskState] = {}
scrcpy_clients: dict[str, list[Any]] = {}
SCRCPY_MAX_SIZE = 1080  # 限制最大边长 1080，防止窗口超出屏幕
WINDOWS_DRIVER_ROOT = "D:\\"
SCRCPY_RECONNECT_INITIAL_DELAY_SECONDS = 2.0
SCRCPY_RECONNECT_MAX_DELAY_SECONDS = 15.0
SCRCPY_RECONNECT_MAX_ATTEMPTS = 1
SCRCPY_ADB_RECONNECT_TIMEOUT_SECONDS = 45.0


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


def _scan_drive_root_scrcpy_candidates(root: str = WINDOWS_DRIVER_ROOT) -> dict[str, list[str]]:
    candidates: dict[str, list[str]] = {"scrcpy": [], "qtscrcpy": []}
    if not os.path.isdir(root):
        return candidates

    def add_if_file(path: str, key: str) -> None:
        if os.path.isfile(path):
            candidates[key].append(path)

    add_if_file(os.path.join(root, "scrcpy.exe"), "scrcpy")
    add_if_file(os.path.join(root, "QtScrcpy.exe"), "qtscrcpy")
    try:
        entries = list(os.scandir(root))
    except OSError:
        return candidates
    for entry in entries:
        try:
            if not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        add_if_file(os.path.join(entry.path, "scrcpy.exe"), "scrcpy")
        add_if_file(os.path.join(entry.path, "QtScrcpy.exe"), "qtscrcpy")
    return candidates


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


def _ensure_scrcpy_driver_available() -> None:
    if _user_scrcpy_path:
        return
    if _get_scrcpy_exe() or _get_qtscrcpy_exe():
        return
    raise FileNotFoundError("未找到 scrcpy.exe 或 QtScrcpy.exe，请安装命令行 scrcpy，或保留仓库内 QtScrcpy。")


def _format_bit_rate(bit_rate: int) -> str:
    if bit_rate >= 1_000_000 and bit_rate % 1_000_000 == 0:
        return f"{bit_rate // 1_000_000}M"
    if bit_rate >= 1_000 and bit_rate % 1_000 == 0:
        return f"{bit_rate // 1_000}K"
    return str(bit_rate)


def _append_optional_window_options(command: list[str]) -> None:
    option_map = {
        "JLAO_SCRCPY_WINDOW_X": "--window-x",
        "JLAO_SCRCPY_WINDOW_Y": "--window-y",
        "JLAO_SCRCPY_WINDOW_WIDTH": "--window-width",
        "JLAO_SCRCPY_WINDOW_HEIGHT": "--window-height",
    }
    for env_name, flag in option_map.items():
        value = os.getenv(env_name, "").strip()
        if value:
            command.extend([flag, value])


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

    command.append("--no-audio")
    max_fps = int(os.getenv("JLAO_SCRCPY_MAX_FPS", "20") or "20")
    if max_fps > 0:
        command.extend(["--max-fps", str(max_fps)])
    command.extend(["--window-title", f"JLAO Projection - {cleaned_serial or 'default-device'}"])
    _append_optional_window_options(command)
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


async def _scrcpy_supervisor(session_id: str) -> None:
    task_state = scrcpy_tasks.get(session_id)
    if not task_state:
        return

    reconnect_delay = SCRCPY_RECONNECT_INITIAL_DELAY_SECONDS
    first_launch = True
    try:
        while task_state.running:
            if not first_launch:
                task_state.reconnecting = True
                task_state.last_error = "投屏已断开，正在自动重连..."

            launch: ScrcpyLaunch | None = None
            stderr_task: asyncio.Task[str] | None = None
            proc: asyncio.subprocess.Process | None = None
            try:
                launch = _build_scrcpy_command(task_state.serial, task_state.max_size, task_state.bit_rate)
                task_state.mode = launch.mode
                task_state.recording_path = ""
                print(f"[scrcpy {session_id}] Starting native window ({launch.mode}): {' '.join(launch.command)}")

                proc = await asyncio.create_subprocess_exec(
                    *launch.command,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=launch.cwd,
                )
                task_state.process = proc
                stderr_task = asyncio.create_task(_read_stderr(proc, session_id))

                await asyncio.sleep(0.8)
                if proc.returncode is None:
                    task_state.reconnecting = False
                    task_state.last_exit_code = None
                    task_state.last_error = ""
                    reconnect_delay = SCRCPY_RECONNECT_INITIAL_DELAY_SECONDS
                    if not first_launch:
                        print(f"[scrcpy {session_id}] Reconnected after {task_state.reconnect_attempts} attempt(s)")
                return_code = await proc.wait()
                stderr_text = await stderr_task
                task_state.last_exit_code = return_code
                if task_state.process is proc:
                    task_state.process = None

                if not task_state.running:
                    break

                if launch.mode != "scrcpy":
                    task_state.running = False
                    task_state.reconnecting = False
                    task_state.last_error = stderr_text or "QtScrcpy 窗口已关闭"
                    break

                task_state.reconnect_attempts += 1
                if return_code != 0:
                    task_state.last_error = stderr_text or f"scrcpy 已退出，退出码：{return_code}，正在自动重连..."
                else:
                    task_state.last_error = "scrcpy 窗口已关闭，正在自动重连..."
                task_state.reconnecting = True
                print(
                    f"[scrcpy {session_id}] exited code={return_code}; "
                    f"auto reconnect attempt={task_state.reconnect_attempts} delay={reconnect_delay:.0f}s"
                )
                if task_state.reconnect_attempts > SCRCPY_RECONNECT_MAX_ATTEMPTS:
                    task_state.running = False
                    task_state.reconnecting = False
                    task_state.last_error = stderr_text or f"scrcpy exited code={return_code}; reconnect limit reached"
                    break
            except asyncio.CancelledError:
                if stderr_task:
                    stderr_task.cancel()
                raise
            except Exception as exc:
                task_state.process = None
                task_state.reconnect_attempts += 1
                task_state.reconnecting = True
                task_state.last_error = f"投屏启动失败，正在自动重连：{exc}"
                print(f"[scrcpy {session_id}] start failed; auto reconnect attempt={task_state.reconnect_attempts}: {exc}")
                if task_state.reconnect_attempts > SCRCPY_RECONNECT_MAX_ATTEMPTS:
                    task_state.running = False
                    task_state.reconnecting = False
                    task_state.last_error = f"scrcpy start failed; reconnect limit reached: {exc}"
                    break

            if not task_state.running:
                break

            await _recover_scrcpy_before_retry(task_state, reconnect_delay)
            reconnect_delay = min(SCRCPY_RECONNECT_MAX_DELAY_SECONDS, reconnect_delay * 1.5)
            first_launch = False
    finally:
        task_state.reconnecting = False


async def _recover_scrcpy_before_retry(task_state: ScrcpyTaskState, delay_seconds: float) -> None:
    scrcpy_exe = _get_scrcpy_exe()
    if scrcpy_exe:
        try:
            await _recover_adb_device(task_state.serial, scrcpy_exe)
        except Exception as exc:
            task_state.last_error = f"ADB 自动重连失败，继续等待：{exc}"
            print(f"[scrcpy {task_state.session_id}] adb recover failed: {exc}")
    await asyncio.sleep(delay_seconds)


async def _recover_adb_device(serial: str, scrcpy_exe: str) -> None:
    adb_exe = _adb_exe_for_scrcpy(scrcpy_exe)
    await _run_adb_command(adb_exe, serial, ["reconnect", "offline"], timeout=10.0, allow_failure=True)
    await _run_adb_command(adb_exe, serial, ["reconnect", "device"], timeout=10.0, allow_failure=True)
    await _run_adb_command(adb_exe, serial, ["wait-for-device"], timeout=SCRCPY_ADB_RECONNECT_TIMEOUT_SECONDS)


def _adb_exe_for_scrcpy(scrcpy_exe: str) -> str:
    candidate = Path(scrcpy_exe).with_name("adb.exe" if sys.platform == "win32" else "adb")
    if candidate.exists():
        return str(candidate)
    return "adb"


def _adb_exe_for_projection() -> str:
    scrcpy_exe = _get_scrcpy_exe()
    if scrcpy_exe:
        return _adb_exe_for_scrcpy(scrcpy_exe)
    qtscrcpy_exe = _get_qtscrcpy_exe()
    if qtscrcpy_exe:
        candidate = Path(qtscrcpy_exe).with_name("adb.exe" if sys.platform == "win32" else "adb")
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


def _has_online_adb_device(devices: list[dict[str, str]], serial: str = "") -> bool:
    cleaned_serial = serial.strip()
    if cleaned_serial:
        return any(item["serial"] == cleaned_serial and item["state"] == "device" for item in devices)
    return any(item["state"] == "device" for item in devices)


def _has_offline_adb_device(devices: list[dict[str, str]], serial: str = "") -> bool:
    cleaned_serial = serial.strip()
    if cleaned_serial:
        return any(item["serial"] == cleaned_serial and item["state"] == "offline" for item in devices)
    return any(item["state"] == "offline" for item in devices)


async def _adb_devices(adb_exe: str) -> list[dict[str, str]]:
    process = await asyncio.create_subprocess_exec(
        adb_exe,
        "devices",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=8.0)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.wait()
        raise RuntimeError("读取 adb devices 超时") from exc
    if process.returncode != 0:
        message = (stderr or stdout).decode("utf-8", errors="ignore").strip()
        raise RuntimeError(message or f"adb devices 失败，退出码：{process.returncode}")
    return _parse_adb_devices_output(stdout.decode("utf-8", errors="ignore"))


async def _ensure_adb_device_online(serial: str = "") -> None:
    adb_exe = _adb_exe_for_projection()
    devices = await _adb_devices(adb_exe)
    if _has_online_adb_device(devices, serial):
        return
    if _has_offline_adb_device(devices, serial):
        await _run_adb_command(adb_exe, serial, ["reconnect", "offline"], timeout=10.0, allow_failure=True)
        await _run_adb_command(adb_exe, serial, ["reconnect", "device"], timeout=10.0, allow_failure=True)
        devices = await _adb_devices(adb_exe)
        if _has_online_adb_device(devices, serial):
            return
    if serial.strip():
        raise RuntimeError(f"ADB 设备未在线：{serial.strip()}，请检查 USB 连接和授权")
    raise RuntimeError("ADB 设备未在线，请检查 USB 连接和授权")


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


async def _terminate_process(proc: asyncio.subprocess.Process | None) -> None:
    if proc is None or proc.returncode is not None:
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

    effective_max_size = SCRCPY_MAX_SIZE
    cleaned_serial = serial.strip()
    _ensure_scrcpy_driver_available()
    await _ensure_adb_device_online(cleaned_serial)
    conflicts = await detect_external_scrcpy_processes()
    if conflicts:
        pids = ", ".join(item["process_id"] for item in conflicts[:3])
        raise RuntimeError(f"检测到未由本项目管理的 scrcpy 进程，请先关闭后再采集。PID：{pids}")
    await stop_scrcpy(session_id)
    task_state = ScrcpyTaskState(
        session_id=session_id,
        serial=cleaned_serial,
        max_size=effective_max_size,
        bit_rate=bit_rate,
    )
    scrcpy_tasks[session_id] = task_state
    task_state.task = asyncio.create_task(_scrcpy_supervisor(session_id))

    await asyncio.sleep(0.8)
    return status(session_id)


async def stop_scrcpy(session_id: str) -> dict[str, Any]:
    task_state = scrcpy_tasks.get(session_id)
    if task_state:
        task_state.running = False
        await _terminate_process(task_state.process)
        if task_state.task and not task_state.task.done():
            task_state.task.cancel()
            try:
                await task_state.task
            except asyncio.CancelledError:
                pass
        scrcpy_tasks.pop(session_id, None)
        scrcpy_clients.pop(session_id, None)
    return status(session_id)


async def stop_all_scrcpy() -> None:
    for session_id in list(scrcpy_tasks):
        await stop_scrcpy(session_id)


async def cleanup_stale_scrcpy_processes() -> None:
    if sys.platform != "win32":
        return
    script = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -ieq 'scrcpy.exe' "
        "-and ($_.CommandLine -like '*JLAO Projection*' -or "
        "$_.CommandLine -like '*JLAO 投屏*' -or "
        "($_.CommandLine -like '*--window-title*' -and $_.CommandLine -like '*JLAO*')) } | "
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


def _is_project_scrcpy_command_line(command_line: str) -> bool:
    lowered = (command_line or "").lower()
    return (
        "jlao projection" in lowered
        or "jlao 投屏" in lowered
        or ("--window-title" in lowered and "jlao" in lowered)
        or ("--no-video" in lowered and "--record-format" in lowered and "wav" in lowered)
    )


async def detect_external_scrcpy_processes() -> list[dict[str, str]]:
    if sys.platform != "win32":
        return []
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='scrcpy.exe'\" | "
        "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }"
    )
    try:
        process = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NoProfile",
            "-Command",
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=5.0)
    except Exception:
        return []
    conflicts: list[dict[str, str]] = []
    for raw_line in stdout.decode("utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        process_id, _, command_line = line.partition("\t")
        if command_line and not _is_project_scrcpy_command_line(command_line):
            conflicts.append({"process_id": process_id.strip(), "command_line": command_line.strip()})
    return conflicts


def status(session_id: str) -> dict[str, Any]:
    task_state = scrcpy_tasks.get(session_id)
    if not task_state:
        return {
            "running": False,
            "state": "stopped",
            "serial": "",
            "last_error": "",
            "width": 0,
            "height": 0,
            "recording_path": "",
            "reconnecting": False,
            "reconnect_attempts": 0,
            "last_exit_code": None,
        }
    process_running = bool(task_state.process and task_state.process.returncode is None)
    running = task_state.running and process_running
    if running:
        state = "running"
    elif task_state.reconnecting or (task_state.running and not task_state.last_error):
        state = "starting"
    elif task_state.last_error:
        state = "error"
    else:
        state = "stopped"
    return {
        "running": running,
        "state": state,
        "serial": task_state.serial,
        "last_error": task_state.last_error,
        "width": task_state.width,
        "height": task_state.height,
        "recording_path": task_state.recording_path,
        "reconnecting": task_state.reconnecting,
        "reconnect_attempts": task_state.reconnect_attempts,
        "last_exit_code": task_state.last_exit_code,
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
