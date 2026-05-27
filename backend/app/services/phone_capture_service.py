import asyncio
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.frame_service import create_frame_snapshot
from app.state import WORKSPACE_DIR, app_state

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@dataclass
class PhoneCaptureTaskState:
    session_id: str
    serial: str
    interval_seconds: float
    task: asyncio.Task[None]
    running: bool = True
    last_error: str = ""
    last_frame_id: str | None = None


capture_tasks: dict[str, PhoneCaptureTaskState] = {}

if sys.platform == "win32":
    _ADB_CANDIDATES = [
        r"D:\scrcpy-win64-v3.3.4\adb.exe",
        r"C:\Program Files\scrcpy\adb.exe",
        r"C:\ProgramData\chocolatey\bin\adb.exe",
        r"C:\Users\Administrator\scoop\shims\adb.exe",
    ]
else:
    _ADB_CANDIDATES = [
        "/usr/bin/adb",
        "/usr/local/bin/adb",
        "/opt/android-platform-tools/adb",
    ]


def _get_adb_exe() -> str:
    for candidate in _ADB_CANDIDATES:
        if os.path.exists(candidate):
            return candidate

    path = shutil.which("adb")
    if path:
        return path

    raise FileNotFoundError("未找到 adb，请确认 scrcpy/platform-tools 已安装。")


def _build_adb_command(serial: str, *args: str) -> list[str]:
    command = [_get_adb_exe()]
    cleaned_serial = serial.strip()
    if cleaned_serial:
        command.extend(["-s", cleaned_serial])
    command.extend(args)
    return command


async def capture_once(session_id: str, serial: str) -> dict[str, Any]:
    if session_id not in app_state.sessions:
        raise ValueError("直播会话不存在")

    upload_dir = WORKSPACE_DIR / "uploads" / "frames" / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    raw_image_path = upload_dir / f"{app_state.new_id('phone-raw')}.png"
    image_path = upload_dir / f"{app_state.new_id('phone')}.jpg"

    await _adb_screencap(serial, raw_image_path)
    await _compress_screenshot(raw_image_path, image_path)
    try:
        raw_image_path.unlink(missing_ok=True)
    except Exception:
        pass

    image_url = f"/uploads/frames/{session_id}/{image_path.name}"
    snapshot = await create_frame_snapshot(session_id, image_path, image_url)
    return snapshot.model_dump(mode="json")


async def start_capture(
    session_id: str,
    serial: str,
    interval_seconds: float = 1.0,
) -> dict[str, Any]:
    if session_id not in app_state.sessions:
        raise ValueError("直播会话不存在")

    await stop_capture(session_id)
    cleaned_serial = serial.strip()
    task = asyncio.create_task(capture_loop(session_id, cleaned_serial, interval_seconds))
    capture_tasks[session_id] = PhoneCaptureTaskState(
        session_id=session_id,
        serial=cleaned_serial,
        interval_seconds=interval_seconds,
        task=task,
    )
    return status(session_id)


async def stop_capture(session_id: str) -> dict[str, Any]:
    task_state = capture_tasks.get(session_id)
    if task_state:
        task_state.running = False
        task_state.task.cancel()
        try:
            await task_state.task
        except asyncio.CancelledError:
            pass
        capture_tasks.pop(session_id, None)
    return status(session_id)


def status(session_id: str) -> dict[str, Any]:
    task_state = capture_tasks.get(session_id)
    if not task_state:
        return {
            "running": False,
            "serial": "",
            "interval_seconds": 1.0,
            "last_error": "",
            "last_frame_id": None,
        }
    return {
        "running": task_state.running and not task_state.task.done(),
        "serial": task_state.serial,
        "interval_seconds": task_state.interval_seconds,
        "last_error": task_state.last_error,
        "last_frame_id": task_state.last_frame_id,
    }


async def capture_loop(session_id: str, serial: str, interval_seconds: float) -> None:
    while True:
        task_state = capture_tasks.get(session_id)
        if not task_state or not task_state.running:
            return

        started_at = asyncio.get_running_loop().time()
        try:
            frame = await capture_once(session_id, serial)
            task_state.last_frame_id = str(frame.get("id") or "")
            task_state.last_error = ""
        except Exception as exc:
            task_state.last_error = str(exc)
            print(f"[phone-capture {session_id}] {exc}")

        elapsed = asyncio.get_running_loop().time() - started_at
        await asyncio.sleep(max(0.1, interval_seconds - elapsed))


async def _adb_screencap(serial: str, image_path: Path) -> None:
    command = _build_adb_command(serial, "exec-out", "screencap", "-p")
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=8)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise RuntimeError("手机截屏超时，请确认设备已连接并授权 USB 调试。") from exc

    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(message or f"adb screencap 失败，退出码：{process.returncode}")

    if not stdout:
        raise RuntimeError("adb screencap 未返回图片数据")

    image_path.write_bytes(stdout)
    if image_path.stat().st_size == 0:
        raise RuntimeError("手机截屏文件为空")


async def _compress_screenshot(raw_image_path: Path, image_path: Path) -> None:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow 未安装，无法压缩手机截图") from exc

    def convert() -> None:
        with Image.open(raw_image_path) as image:
            image.thumbnail((576, 1024), Image.Resampling.LANCZOS)
            rgb_image = image.convert("RGB")
            rgb_image.save(image_path, format="JPEG", quality=72, optimize=True, progressive=True)

    await asyncio.to_thread(convert)

    if not image_path.exists() or image_path.stat().st_size == 0:
        raise RuntimeError("手机截图压缩失败")
