from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.repositories import save_live_session
from app.schemas import SessionStatus
from app.state import app_state
from app.ws.manager import manager

logger = logging.getLogger(__name__)


@dataclass
class FrontendResourceState:
    session_id: str
    running: bool = False
    state: str = "stopped"
    last_error: str = ""
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


browser_video_states: dict[str, FrontendResourceState] = {}
ocr_capture_states: dict[str, FrontendResourceState] = {}


def mark_browser_video(session_id: str, running: bool, *, last_error: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    if running:
        require_projection_running(session_id)
    state = _set_frontend_resource(browser_video_states, session_id, running, last_error=last_error, metadata=metadata)
    logger.info("[capture-resource %s] browser_video_stream=%s error=%s", session_id, state.state, last_error)
    return _frontend_resource_status(state)


def mark_ocr_capture(session_id: str, running: bool, *, last_error: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    if running:
        require_browser_video_running(session_id)
    state = _set_frontend_resource(ocr_capture_states, session_id, running, last_error=last_error, metadata=metadata)
    logger.info("[capture-resource %s] ocr_capture=%s error=%s", session_id, state.state, last_error)
    return _frontend_resource_status(state)


def is_browser_video_running(session_id: str) -> bool:
    state = browser_video_states.get(session_id)
    return bool(state and state.running and state.state == "running")


def is_ocr_capture_running(session_id: str) -> bool:
    state = ocr_capture_states.get(session_id)
    return bool(state and state.running and state.state == "running")


def require_projection_running(session_id: str) -> None:
    from app.services import scrcpy_service

    try:
        from app.services import capture_card_service
    except Exception:
        capture_card_running = False
    else:
        capture_card_running = bool(capture_card_service.status(session_id).get("running"))

    if not scrcpy_service.status(session_id).get("running") and not capture_card_running:
        raise RuntimeError("请先启动采集投屏")


def require_browser_video_running(session_id: str) -> None:
    if not is_browser_video_running(session_id):
        raise RuntimeError("请先接入视频流")


def projection_dependents(session_id: str) -> list[str]:
    dependents: list[str] = []
    if is_browser_video_running(session_id):
        dependents.append("视频流")
    if is_ocr_capture_running(session_id):
        dependents.append("截图/OCR")
    recorder_status = _recorder_status(session_id)
    if recorder_status.get("running"):
        dependents.append("录屏")
    return dependents


def aggregate_status(session_id: str) -> dict[str, Any]:
    from app.services import capture_card_service, native_audio_service, native_stt_service, scrcpy_service

    scrcpy = scrcpy_service.status(session_id)
    capture_card = capture_card_service.status(session_id)
    native_audio = native_audio_service.status(session_id)
    native_stt = native_stt_service.status(session_id)
    browser_video = _frontend_resource_status(browser_video_states.get(session_id))
    ocr_capture = _frontend_resource_status(ocr_capture_states.get(session_id))
    recorder = _recorder_status(session_id)

    return {
        "status": "ok",
        "session_id": session_id,
        "resources": {
            "scrcpy_projection": _scrcpy_resource_status(scrcpy),
            "capture_card_input": _capture_card_resource_status(capture_card),
            "browser_video_stream": browser_video,
            "native_audio_stream": _native_audio_resource_status(native_audio),
            "native_stt": _native_stt_resource_status(native_stt),
            "ocr_capture": ocr_capture,
            "recorder": recorder,
        },
        "legacy": {
            "scrcpy": scrcpy,
            "capture_card": capture_card,
            "native_audio": native_audio,
            "native_stt": native_stt,
        },
    }


async def broadcast_status(session_id: str) -> None:
    await manager.broadcast(session_id, "capture_status", aggregate_status(session_id))


async def soft_reset(session_id: str | None = None) -> dict[str, Any]:
    from app.services import capture_card_service, native_audio_service, native_stt_service, phone_capture_service, scrcpy_service

    session_ids = _target_session_ids(session_id)
    logger.info("[capture-resource] soft reset sessions=%s", session_ids)
    for sid in session_ids:
        await _stop_recorder_if_available(sid, abort=True)
        await native_stt_service.stop_native_stt(sid)
        await phone_capture_service.stop_capture(sid)
        await capture_card_service.stop_preview(sid)
        await native_audio_service.stop_native_audio(sid, force=True)
        await scrcpy_service.stop_scrcpy(sid)
        await _stop_live_session(sid)
        browser_video_states.pop(sid, None)
        ocr_capture_states.pop(sid, None)
        await broadcast_status(sid)
    return {"status": "ok", "reset": "soft", "sessions": session_ids}


async def hard_reset(session_id: str | None = None) -> dict[str, Any]:
    from app.services import native_audio_service, scrcpy_service

    result = await soft_reset(session_id)
    logger.info("[capture-resource] hard reset cleanup")
    cleanup: list[dict[str, str]] = []
    await _run_hard_reset_action(
        cleanup,
        "scrcpy",
        "清理本项目残留 scrcpy 进程",
        scrcpy_service.cleanup_stale_scrcpy_processes,
    )
    await _run_hard_reset_action(
        cleanup,
        "native_audio",
        "清理本项目残留音频采集进程",
        native_audio_service.cleanup_stale_native_audio_processes,
    )
    await _run_hard_reset_action(
        cleanup,
        "adb_reconnect",
        "ADB offline 自动重连一次",
        lambda: native_audio_service.recover_adb_once(""),
    )
    adb_status = await native_audio_service.get_adb_devices_status()
    logger.info("[capture-resource] hard reset adb status: %s", adb_status)
    return {**result, "reset": "hard", "cleanup": cleanup, "adb_status": adb_status}


async def startup_reset() -> None:
    logger.info("[capture-resource] startup reset")
    browser_video_states.clear()
    ocr_capture_states.clear()
    await hard_reset(None)


def _set_frontend_resource(
    target: dict[str, FrontendResourceState],
    session_id: str,
    running: bool,
    *,
    last_error: str = "",
    metadata: dict[str, Any] | None = None,
) -> FrontendResourceState:
    state = target.get(session_id)
    if state is None:
        state = FrontendResourceState(session_id=session_id)
        target[session_id] = state
    state.running = running
    state.state = "running" if running else ("error" if last_error else "stopped")
    state.last_error = last_error
    state.updated_at = time.time()
    state.metadata = metadata or {}
    if not running and not last_error:
        target.pop(session_id, None)
    return state


def _frontend_resource_status(state: FrontendResourceState | None) -> dict[str, Any]:
    if not state:
        return {"running": False, "state": "stopped", "last_error": "", "updated_at": 0, "metadata": {}}
    return {
        "running": state.running,
        "state": state.state,
        "last_error": state.last_error,
        "updated_at": state.updated_at,
        "metadata": state.metadata,
    }


def _scrcpy_resource_status(info: dict[str, Any]) -> dict[str, Any]:
    running = bool(info.get("running"))
    last_error = str(info.get("last_error") or "")
    if running:
        state = "starting" if info.get("reconnecting") else "running"
    else:
        state = "error" if last_error else "stopped"
    return {
        "running": running,
        "state": state,
        "last_error": last_error,
        "serial": info.get("serial") or "",
        "reconnecting": bool(info.get("reconnecting")),
        "reconnect_attempts": int(info.get("reconnect_attempts") or 0),
    }


def _capture_card_resource_status(info: dict[str, Any]) -> dict[str, Any]:
    running = bool(info.get("running"))
    last_error = str(info.get("last_error") or "")
    return {
        "running": running,
        "state": info.get("state") or ("running" if running else ("error" if last_error else "stopped")),
        "last_error": last_error,
        "device_id": info.get("device_id") or "",
        "video_index": int(info.get("video_index") or 0),
        "width": int(info.get("width") or 0),
        "height": int(info.get("height") or 0),
        "fps": int(info.get("fps") or 0),
        "frame_width": int(info.get("frame_width") or 0),
        "frame_height": int(info.get("frame_height") or 0),
        "frame_mean": float(info.get("frame_mean") or 0.0),
        "frame_std": float(info.get("frame_std") or 0.0),
        "signal_present": bool(info.get("signal_present")),
        "frame_count": int(info.get("frame_count") or 0),
    }


def _native_audio_resource_status(info: dict[str, Any]) -> dict[str, Any]:
    return {
        "running": bool(info.get("running")),
        "state": info.get("state") or ("running" if info.get("running") else "stopped"),
        "last_error": info.get("last_error") or "",
        "serial": info.get("serial") or "",
        "source": info.get("source") or "playback",
        "device_id": info.get("device_id") or "",
        "device_name": info.get("device_name") or "",
        "audio_chunks": int(info.get("audio_chunks") or 0),
        "audio_bytes": int(info.get("audio_bytes") or 0),
        "consumers": list(info.get("consumers") or []),
    }


def _native_stt_resource_status(info: dict[str, Any]) -> dict[str, Any]:
    running = bool(info.get("running"))
    last_error = str(info.get("last_error") or "")
    return {
        "running": running,
        "state": "running" if running else ("error" if last_error else "stopped"),
        "last_error": last_error,
        "provider": info.get("provider") or "local",
        "audio_chunks": int(info.get("audio_chunks") or 0),
        "audio_bytes": int(info.get("audio_bytes") or 0),
        "transcript_segments": int(info.get("transcript_segments") or 0),
    }


def _recorder_status(session_id: str) -> dict[str, Any]:
    try:
        from app.services import recording_service
    except Exception:
        return {"running": False, "state": "stopped", "last_error": ""}
    return recording_service.status(session_id)


async def _stop_recorder_if_available(session_id: str, *, abort: bool = False) -> None:
    try:
        from app.services import recording_service
    except Exception:
        return
    await recording_service.stop_recording(session_id, abort=abort)


def _target_session_ids(session_id: str | None) -> list[str]:
    if session_id:
        return [session_id]
    ids = set(app_state.sessions)
    ids.update(browser_video_states)
    ids.update(ocr_capture_states)
    try:
        from app.services import native_audio_service, native_stt_service, phone_capture_service, scrcpy_service

        ids.update(scrcpy_service.scrcpy_tasks)
        try:
            from app.services import capture_card_service

            ids.update(capture_card_service.preview_states)
        except Exception:
            pass
        ids.update(native_audio_service.native_audio_streams)
        ids.update(native_stt_service.native_stt_tasks)
        ids.update(phone_capture_service.capture_tasks)
    except Exception:
        pass
    try:
        from app.services import recording_service

        ids.update(recording_service.recording_tasks)
    except Exception:
        pass
    return sorted(ids)


async def _stop_live_session(session_id: str) -> None:
    session = app_state.sessions.get(session_id)
    if not session:
        return
    if session.status == SessionStatus.stopped:
        return
    now = datetime.now(timezone.utc)
    updated = session.model_copy(
        update={
            "status": SessionStatus.stopped,
            "end_time": now,
            "updated_at": now,
        }
    )
    app_state.sessions[session_id] = updated
    save_live_session(updated)
    await manager.broadcast(session_id, "session_status", updated.model_dump(mode="json"))


async def _run_hard_reset_action(
    cleanup: list[dict[str, str]],
    name: str,
    label: str,
    action,
) -> None:
    try:
        await action()
        cleanup.append({"name": name, "status": "ok", "message": label})
        logger.info("[capture-resource] hard reset action ok: %s", label)
    except Exception as exc:
        cleanup.append({"name": name, "status": "error", "message": f"{label}失败：{exc}"})
        logger.exception("[capture-resource] hard reset action failed: %s", label)
