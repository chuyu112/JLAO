from __future__ import annotations

import asyncio
import json
import platform
import re
import sys
import time
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any


VIDEO_PNP_CLASSES = {"camera", "image"}
AUDIO_PNP_CLASSES = {"audioendpoint", "media"}
CAPTURE_KEYWORDS = (
    "capture",
    "hdmi",
    "ugreen",
    "usb video",
    "uvc",
    "cam link",
    "avermedia",
    "ezcap",
    "采集",
    "视频采集",
)
NON_CAPTURE_AUDIO_NAMES = (
    "nvidia",
    "amd streaming",
    "high definition audio",
    "realtek",
)
DEFAULT_PREVIEW_WIDTH = 1280
DEFAULT_PREVIEW_HEIGHT = 720
DEFAULT_PREVIEW_FPS = 30
MAX_PREVIEW_FPS = 60
MJPEG_BOUNDARY = "frame"


@dataclass
class CaptureCardPreviewState:
    session_id: str
    device_id: str = ""
    video_index: int = 0
    width: int = DEFAULT_PREVIEW_WIDTH
    height: int = DEFAULT_PREVIEW_HEIGHT
    fps: int = DEFAULT_PREVIEW_FPS
    running: bool = False
    state: str = "stopped"
    last_error: str = ""
    frame_width: int = 0
    frame_height: int = 0
    frame_mean: float = 0.0
    frame_std: float = 0.0
    signal_present: bool = False
    frame_count: int = 0
    started_at: float = 0.0
    updated_at: float = field(default_factory=time.time)
    task: asyncio.Task | None = None
    stop_event: asyncio.Event | None = None
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    latest_jpeg: bytes = b""


preview_states: dict[str, CaptureCardPreviewState] = {}


async def enumerate_devices() -> dict[str, Any]:
    errors: list[str] = []
    raw_devices: list[dict[str, Any]] = []

    if sys.platform == "win32":
        wmi_error = ""
        try:
            raw_devices = await _enumerate_windows_pnp_devices()
        except Exception as exc:  # noqa: BLE001
            wmi_error = str(exc)
        if not raw_devices:
            try:
                raw_devices = await _enumerate_windows_pnputil_devices()
            except Exception as exc:  # noqa: BLE001
                details = f"{wmi_error}; pnputil: {exc}" if wmi_error else str(exc)
                errors.append(f"Windows 设备枚举失败：{details}")
    else:
        errors.append(f"当前平台暂未实现采集卡设备枚举：{platform.system() or sys.platform}")

    return build_device_result(raw_devices, platform_name=sys.platform, errors=errors)


async def start_preview(
    session_id: str,
    *,
    device_id: str = "",
    video_index: int | None = None,
    width: int = DEFAULT_PREVIEW_WIDTH,
    height: int = DEFAULT_PREVIEW_HEIGHT,
    fps: int = DEFAULT_PREVIEW_FPS,
) -> dict[str, Any]:
    await stop_preview(session_id)
    devices = await enumerate_devices()
    selected_index = _resolve_video_index(devices.get("video_devices") or [], device_id=device_id, video_index=video_index)
    normalized_fps = max(1, min(MAX_PREVIEW_FPS, int(fps or DEFAULT_PREVIEW_FPS)))
    state = CaptureCardPreviewState(
        session_id=session_id,
        device_id=device_id,
        video_index=selected_index,
        width=max(160, int(width or DEFAULT_PREVIEW_WIDTH)),
        height=max(120, int(height or DEFAULT_PREVIEW_HEIGHT)),
        fps=normalized_fps,
        running=True,
        state="starting",
        started_at=time.time(),
        updated_at=time.time(),
        stop_event=asyncio.Event(),
    )
    preview_states[session_id] = state
    state.task = asyncio.create_task(_preview_loop(state))

    deadline = time.time() + 3.0
    while time.time() < deadline:
        if state.frame_count > 0:
            return status(session_id)
        if state.state == "error":
            break
        await asyncio.sleep(0.05)
    return status(session_id)


async def stop_preview(session_id: str) -> dict[str, Any]:
    state = preview_states.get(session_id)
    if not state:
        return _empty_preview_status(session_id)
    state.running = False
    state.state = "stopping"
    state.updated_at = time.time()
    if state.stop_event:
        state.stop_event.set()
    if state.task:
        try:
            await asyncio.wait_for(state.task, timeout=3.0)
        except asyncio.TimeoutError:
            state.task.cancel()
        except Exception:
            pass
    preview_states.pop(session_id, None)
    return _empty_preview_status(session_id)


async def stop_all_previews() -> None:
    for session_id in list(preview_states):
        await stop_preview(session_id)


def status(session_id: str) -> dict[str, Any]:
    state = preview_states.get(session_id)
    if not state:
        return _empty_preview_status(session_id)
    return {
        "running": bool(state.running),
        "state": state.state,
        "session_id": session_id,
        "device_id": state.device_id,
        "video_index": state.video_index,
        "width": state.width,
        "height": state.height,
        "fps": state.fps,
        "frame_width": state.frame_width,
        "frame_height": state.frame_height,
        "frame_mean": round(state.frame_mean, 2),
        "frame_std": round(state.frame_std, 2),
        "signal_present": state.signal_present,
        "frame_count": state.frame_count,
        "last_error": state.last_error,
        "started_at": state.started_at,
        "updated_at": state.updated_at,
    }


async def snapshot(session_id: str) -> bytes:
    state = preview_states.get(session_id)
    if not state or not state.running:
        raise RuntimeError("采集卡预览未启动")
    frame = await _wait_for_frame(state, last_count=-1, timeout=2.0)
    if not frame:
        raise RuntimeError(state.last_error or "采集卡暂未输出画面")
    return frame


async def transformed_snapshot(session_id: str, *, rotation: int = 0, mirror: bool = False) -> bytes:
    frame = await snapshot(session_id)
    if _normalize_rotation(rotation) == 0 and not mirror:
        return frame
    return await asyncio.to_thread(transform_jpeg_bytes, frame, rotation=rotation, mirror=mirror)


def transform_jpeg_bytes(data: bytes, *, rotation: int = 0, mirror: bool = False, quality: int = 82) -> bytes:
    rotation = _normalize_rotation(rotation)
    if rotation == 0 and not mirror:
        return data
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is required to transform capture-card snapshots") from exc

    with Image.open(BytesIO(data)) as image:
        output_image = image.convert("RGB")
        if mirror:
            output_image = ImageOps.mirror(output_image)
        if rotation == 90:
            output_image = output_image.transpose(Image.Transpose.ROTATE_270)
        elif rotation == 180:
            output_image = output_image.transpose(Image.Transpose.ROTATE_180)
        elif rotation == 270:
            output_image = output_image.transpose(Image.Transpose.ROTATE_90)
        output = BytesIO()
        output_image.save(output, format="JPEG", quality=max(1, min(95, int(quality or 82))))
        return output.getvalue()


async def mjpeg_stream(session_id: str):
    state = preview_states.get(session_id)
    if not state or not state.running:
        raise RuntimeError("采集卡预览未启动")
    last_count = -1
    while state.running:
        frame = await _wait_for_frame(state, last_count=last_count, timeout=2.0)
        if not frame:
            if state.state == "error":
                break
            continue
        last_count = state.frame_count
        yield (
            f"--{MJPEG_BOUNDARY}\r\n"
            "Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(frame)}\r\n\r\n"
        ).encode("ascii") + frame + b"\r\n"


def _empty_preview_status(session_id: str) -> dict[str, Any]:
    return {
        "running": False,
        "state": "stopped",
        "session_id": session_id,
        "device_id": "",
        "video_index": 0,
        "width": 0,
        "height": 0,
        "fps": 0,
        "frame_width": 0,
        "frame_height": 0,
        "frame_mean": 0.0,
        "frame_std": 0.0,
        "signal_present": False,
        "frame_count": 0,
        "last_error": "",
        "started_at": 0,
        "updated_at": 0,
    }


async def _preview_loop(state: CaptureCardPreviewState) -> None:
    cap = None
    try:
        import cv2

        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        cap = cv2.VideoCapture(state.video_index, backend)
        if not cap.isOpened():
            raise RuntimeError(f"无法打开采集卡视频设备 index={state.video_index}")

        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, state.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, state.height)
        cap.set(cv2.CAP_PROP_FPS, state.fps)

        state.state = "running"
        state.last_error = ""
        state.updated_at = time.time()
        frame_delay = 1.0 / max(1, state.fps)
        while state.running and not (state.stop_event and state.stop_event.is_set()):
            started = time.time()
            ok, frame = await asyncio.to_thread(cap.read)
            if not ok or frame is None:
                state.last_error = "采集卡没有输出视频帧"
                state.state = "error"
                state.running = False
                state.updated_at = time.time()
                break

            ok, encoded = await asyncio.to_thread(cv2.imencode, ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            if not ok:
                state.last_error = "采集卡视频帧编码失败"
                state.state = "error"
                state.running = False
                state.updated_at = time.time()
                break

            async with state.condition:
                state.latest_jpeg = encoded.tobytes()
                state.frame_height = int(frame.shape[0])
                state.frame_width = int(frame.shape[1])
                state.frame_mean = float(frame.mean())
                state.frame_std = float(frame.std())
                state.signal_present = _has_visual_signal(state.frame_mean, state.frame_std)
                state.frame_count += 1
                state.updated_at = time.time()
                state.condition.notify_all()

            elapsed = time.time() - started
            if elapsed < frame_delay:
                await asyncio.sleep(frame_delay - elapsed)
    except Exception as exc:  # noqa: BLE001
        state.running = False
        state.state = "error"
        state.last_error = str(exc)
        state.updated_at = time.time()
        async with state.condition:
            state.condition.notify_all()
    finally:
        if cap is not None:
            await asyncio.to_thread(cap.release)
        if state.state == "stopping":
            state.state = "stopped"
        state.running = False if state.state != "running" else state.running
        state.updated_at = time.time()


async def _wait_for_frame(state: CaptureCardPreviewState, *, last_count: int, timeout: float) -> bytes:
    deadline = time.time() + timeout
    async with state.condition:
        while state.running and (not state.latest_jpeg or state.frame_count <= last_count):
            remaining = deadline - time.time()
            if remaining <= 0:
                return b""
            try:
                await asyncio.wait_for(state.condition.wait(), timeout=remaining)
            except asyncio.TimeoutError:
                return b""
        return state.latest_jpeg


def _resolve_video_index(
    video_devices: list[dict[str, Any]],
    *,
    device_id: str = "",
    video_index: int | None = None,
) -> int:
    if video_index is not None:
        return max(0, int(video_index))
    if not video_devices:
        return 0
    if device_id:
        for index, device in enumerate(video_devices):
            if device_id in {str(device.get("id") or ""), str(device.get("device_id") or "")}:
                return index
    for index, device in enumerate(video_devices):
        if device.get("is_capture_candidate"):
            return index
    return 0


def _has_visual_signal(frame_mean: float, frame_std: float) -> bool:
    return frame_std > 3.0 or frame_mean > 25.0


def _normalize_rotation(value: int) -> int:
    try:
        rotation = int(value or 0) % 360
    except (TypeError, ValueError):
        return 0
    return rotation if rotation in {0, 90, 180, 270} else 0


def build_device_result(
    raw_devices: list[dict[str, Any]],
    *,
    platform_name: str,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    video_devices: list[dict[str, Any]] = []
    audio_devices: list[dict[str, Any]] = []

    for index, raw in enumerate(raw_devices):
        normalized = _normalize_device(raw, index)
        pnp_class = normalized["pnp_class"].lower()
        if pnp_class in VIDEO_PNP_CLASSES:
            video_devices.append(normalized)
        if _is_audio_device(normalized):
            audio_devices.append(normalized)

    return {
        "status": "ok" if not errors else ("partial" if raw_devices else "error"),
        "platform": platform_name,
        "video_devices": _sort_devices(video_devices, preferred_classes=("camera", "image")),
        "audio_devices": _sort_devices(audio_devices, preferred_classes=("audioendpoint", "media")),
        "raw_count": len(raw_devices),
        "errors": errors or [],
    }


async def _enumerate_windows_pnp_devices() -> list[dict[str, Any]]:
    script = r"""
$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$devices = Get-CimInstance Win32_PnPEntity |
  Where-Object {
    $_.Present -ne $false -and
    $_.PNPClass -in @('Camera', 'Image', 'MEDIA', 'AudioEndpoint')
  } |
  Select-Object `
    @{Name='pnp_class'; Expression={$_.PNPClass}},
    @{Name='name'; Expression={$_.Name}},
    @{Name='status'; Expression={$_.Status}},
    @{Name='device_id'; Expression={$_.DeviceID}},
    @{Name='manufacturer'; Expression={$_.Manufacturer}},
    @{Name='service'; Expression={$_.Service}}
@($devices) | ConvertTo-Json -Depth 4
"""
    process = await asyncio.create_subprocess_exec(
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=8.0)
    text = stdout.decode("utf-8", errors="replace").strip()
    error_text = stderr.decode("utf-8", errors="replace").strip()
    if process.returncode != 0:
        raise RuntimeError(error_text or f"PowerShell 退出码 {process.returncode}")
    if not text:
        return []
    payload = json.loads(text)
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


async def _enumerate_windows_pnputil_devices() -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    for class_name in ("Camera", "Image", "AudioEndpoint", "MEDIA"):
        output = await _run_pnputil_enum_devices(class_name)
        devices.extend(parse_pnputil_devices(output))

    deduped: dict[str, dict[str, Any]] = {}
    for device in devices:
        key = str(device.get("device_id") or device.get("name") or "")
        if key:
            deduped[key] = device
    return list(deduped.values())


async def _run_pnputil_enum_devices(class_name: str) -> str:
    process = await asyncio.create_subprocess_exec(
        "pnputil",
        "/enum-devices",
        "/connected",
        "/class",
        class_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=8.0)
    if process.returncode != 0:
        raise RuntimeError(_decode_windows_output(stderr) or f"pnputil 退出码 {process.returncode}")
    return _decode_windows_output(stdout)


def parse_pnputil_devices(text: str) -> list[dict[str, Any]]:
    field_map = {
        "Instance ID": "device_id",
        "Device Description": "name",
        "Class Name": "pnp_class",
        "Manufacturer Name": "manufacturer",
        "Status": "status",
        "Driver Name": "service",
    }
    devices: list[dict[str, Any]] = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        mapped = field_map.get(key.strip())
        if not mapped:
            continue
        if mapped == "device_id" and current:
            devices.append(current)
            current = {}
        current[mapped] = value.strip()
    if current:
        devices.append(current)
    return devices


def _normalize_device(raw: dict[str, Any], index: int) -> dict[str, Any]:
    name = _clean_text(raw.get("name"))
    pnp_class = _clean_text(raw.get("pnp_class"))
    device_id = _clean_text(raw.get("device_id"))
    status = _clean_text(raw.get("status"))
    manufacturer = _clean_text(raw.get("manufacturer"))
    service = _clean_text(raw.get("service"))
    return {
        "id": device_id or f"{pnp_class}:{name}:{index}",
        "name": name,
        "pnp_class": pnp_class,
        "status": status,
        "device_id": device_id,
        "manufacturer": manufacturer,
        "service": service,
        "is_capture_candidate": _is_capture_candidate(name, device_id, manufacturer),
    }


def _is_audio_device(device: dict[str, Any]) -> bool:
    pnp_class = device["pnp_class"].lower()
    if pnp_class == "audioendpoint":
        return True
    if pnp_class != "media":
        return False
    name = str(device.get("name") or "").lower()
    return _is_capture_candidate(str(device.get("name") or ""), str(device.get("device_id") or ""), str(device.get("manufacturer") or "")) or any(
        keyword in name for keyword in ("audio", "音频", "microphone", "麦克风")
    )


def _is_capture_candidate(name: str, device_id: str = "", manufacturer: str = "") -> bool:
    haystack = f"{name} {device_id} {manufacturer}".lower()
    return any(keyword in haystack for keyword in CAPTURE_KEYWORDS)


def _sort_devices(devices: list[dict[str, Any]], *, preferred_classes: tuple[str, ...]) -> list[dict[str, Any]]:
    return sorted(
        devices,
        key=lambda item: (
            not bool(item.get("is_capture_candidate")),
            _class_rank(str(item.get("pnp_class") or ""), preferred_classes),
            _non_capture_audio_rank(str(item.get("name") or "")),
            str(item.get("name") or "").lower(),
        ),
    )


def _class_rank(pnp_class: str, preferred_classes: tuple[str, ...]) -> int:
    lowered = pnp_class.lower()
    try:
        return preferred_classes.index(lowered)
    except ValueError:
        return len(preferred_classes)


def _non_capture_audio_rank(name: str) -> int:
    lowered = name.lower()
    return 1 if any(keyword in lowered for keyword in NON_CAPTURE_AUDIO_NAMES) else 0


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _decode_windows_output(payload: bytes) -> str:
    for encoding in ("utf-8", "mbcs", "gbk"):
        try:
            return payload.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
        except LookupError:
            continue
    return payload.decode("utf-8", errors="replace").strip()
