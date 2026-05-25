import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import imageio_ffmpeg

from app.services.frame_service import create_frame_snapshot
from app.state import WORKSPACE_DIR, app_state


@dataclass
class CaptureTaskState:
    session_id: str
    source_url: str
    interval_seconds: float
    task: asyncio.Task[None]
    running: bool = True
    last_error: str = ""
    last_frame_id: str | None = None


capture_tasks: dict[str, CaptureTaskState] = {}


async def capture_once(session_id: str, source_url: str) -> dict[str, Any]:
    if session_id not in app_state.sessions:
        raise ValueError("直播会话不存在")
    source = source_url.strip()
    if not source:
        raise ValueError("缺少直播流地址")

    upload_dir = WORKSPACE_DIR / "uploads" / "frames" / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    image_path = upload_dir / f"{app_state.new_id('frame')}.jpg"
    await extract_frame(source, image_path)
    image_url = f"/uploads/frames/{session_id}/{image_path.name}"
    snapshot = await create_frame_snapshot(session_id, image_path, image_url)
    return snapshot.model_dump(mode="json")


async def start_capture(session_id: str, source_url: str, interval_seconds: float) -> dict[str, Any]:
    await stop_capture(session_id)
    task = asyncio.create_task(capture_loop(session_id, source_url, interval_seconds))
    capture_tasks[session_id] = CaptureTaskState(
        session_id=session_id,
        source_url=source_url,
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
        return {"running": False, "last_error": "", "last_frame_id": None}
    return {
        "running": task_state.running and not task_state.task.done(),
        "source_url": task_state.source_url,
        "interval_seconds": task_state.interval_seconds,
        "last_error": task_state.last_error,
        "last_frame_id": task_state.last_frame_id,
    }


async def capture_loop(session_id: str, source_url: str, interval_seconds: float) -> None:
    while True:
        task_state = capture_tasks.get(session_id)
        if not task_state or not task_state.running:
            return
        try:
            frame = await capture_once(session_id, source_url)
            task_state.last_frame_id = str(frame.get("id") or "")
            task_state.last_error = ""
        except Exception as exc:  # noqa: BLE001
            task_state.last_error = str(exc)
        await asyncio.sleep(interval_seconds)


async def extract_frame(source_url: str, image_path: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [
        ffmpeg,
        "-nostdin",
        "-y",
        "-loglevel",
        "error",
        "-i",
        source_url,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(image_path),
    ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=25)
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise RuntimeError("FFmpeg 抽帧超时，请确认是可直接访问的视频流地址") from exc

    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="ignore").strip()
        raise RuntimeError(message or "FFmpeg 抽帧失败")
    if not image_path.exists() or image_path.stat().st_size == 0:
        raise RuntimeError("FFmpeg 没有生成有效截图")
