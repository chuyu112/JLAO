from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.jade_yolo_service import detect_jade_candidates
from app.state import WORKSPACE_DIR, app_state


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


router = APIRouter()
LIVE_YOLO_MIN_CONFIDENCE = _float_env("JLAO_LIVE_YOLO_MIN_CONFIDENCE", 0.01)
LIVE_YOLO_ROI = (0.0, 0.0, 1.0, 1.0)
LIVE_YOLO_CONFIRM_FRAMES = 3
LIVE_YOLO_HOLD_FRAMES = 10
LIVE_YOLO_SWITCH_FRAMES = 8
LIVE_YOLO_MATCH_MIN_IOU = 0.12
LIVE_YOLO_BOX_SMOOTHING = 0.65
LIVE_TRACKER_IDLE_TTL_SECONDS = 600
LIVE_YOLO_SNAPSHOT_ENABLED = os.getenv("JLAO_YOLO_LIVE_SNAPSHOT_ENABLED", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
LIVE_YOLO_SNAPSHOT_INTERVAL_SECONDS = max(
    1.0,
    float(os.getenv("JLAO_YOLO_LIVE_SNAPSHOT_INTERVAL_SECONDS", "30.0") or "30.0"),
)
LIVE_YOLO_SNAPSHOT_MAX_PER_SESSION = max(0, int(os.getenv("JLAO_YOLO_LIVE_SNAPSHOT_MAX_PER_SESSION", "100") or "100"))
LIVE_YOLO_SNAPSHOT_ROOT = WORKSPACE_DIR / "uploads" / "yolo-live-snapshots"
LIVE_YOLO_FEEDBACK_PATH = WORKSPACE_DIR / "data" / "jade_feedback.jsonl"
LIVE_YOLO_SNAPSHOT_MANIFEST_FIELDS = [
    "image",
    "batch_id",
    "feedback_id",
    "session_id",
    "source_frame_id",
    "width",
    "height",
    "created_at",
]
LIVE_YOLO_SNAPSHOT_PETS = (
    "\n".join((
        r" /\_/\ ",
        r"( o.o )",
        r" > ^ < ",
    )),
    "\n".join((
        r"  __  ",
        r" (oo) ",
        "/|__|\\",
    )),
    "\n".join((
        r" .-. ",
        r"(o o)",
        r"| O |",
    )),
)


@dataclass
class LiveYoloTrackingUpdate:
    detections: list[dict[str, Any]]
    tracking: dict[str, Any]


@dataclass
class LiveYoloSnapshotState:
    batch_id: str
    image_dir: Path
    manifest_path: Path
    saved: int = 0
    last_saved_at: float = 0.0


@dataclass
class _LiveTrack:
    track_id: str
    box: list[float]
    detection: dict[str, Any]
    stable_frames: int = 1
    lost_frames: int = 0
    pending_switch_frames: int = 0


@dataclass
class LiveJadeTracker:
    confirm_frames: int = LIVE_YOLO_CONFIRM_FRAMES
    hold_frames: int = LIVE_YOLO_HOLD_FRAMES
    switch_frames: int = LIVE_YOLO_SWITCH_FRAMES
    match_min_iou: float = LIVE_YOLO_MATCH_MIN_IOU
    box_smoothing: float = LIVE_YOLO_BOX_SMOOTHING
    active_tracks: list[_LiveTrack] = field(default_factory=list)
    pending_tracks: list[_LiveTrack] = field(default_factory=list)
    _next_track_number: int = 1
    updated_at: float = field(default_factory=time.monotonic)

    @property
    def active(self) -> _LiveTrack | None:
        return self.active_tracks[0] if self.active_tracks else None

    @property
    def pending(self) -> _LiveTrack | None:
        return self.pending_tracks[0] if self.pending_tracks else None

    def update(self, candidates: list[dict[str, Any]]) -> LiveYoloTrackingUpdate:
        self.updated_at = time.monotonic()
        valid_candidates = [item for item in candidates if _detection_box(item) is not None]

        used_candidate_indexes: set[int] = set()
        if self.active_tracks:
            self._update_active_tracks(valid_candidates, used_candidate_indexes)

        remaining_candidates = [
            candidate for index, candidate in enumerate(valid_candidates)
            if index not in used_candidate_indexes
        ]
        confirmed_tracks = self._update_pending_tracks(remaining_candidates)
        if confirmed_tracks:
            self.active_tracks.extend(confirmed_tracks)

        self.active_tracks.sort(key=lambda track: track.track_id)
        self.pending_tracks.sort(key=lambda track: track.track_id)
        return self._current_update(candidate_count=len(valid_candidates))

    def _update_active_tracks(
        self,
        candidates: list[dict[str, Any]],
        used_candidate_indexes: set[int],
    ) -> None:
        updated_tracks: list[_LiveTrack] = []
        for track in self.active_tracks:
            match_index = _best_matching_detection_index(
                track.box,
                candidates,
                self.match_min_iou,
                used_candidate_indexes,
            )
            if match_index is None:
                track.lost_frames += 1
                track.pending_switch_frames = 0
            else:
                used_candidate_indexes.add(match_index)
                self._update_track(track, candidates[match_index])

            if track.lost_frames <= self.hold_frames:
                updated_tracks.append(track)
        self.active_tracks = updated_tracks

    def _update_pending_tracks(self, candidates: list[dict[str, Any]]) -> list[_LiveTrack]:
        if not candidates:
            self.pending_tracks = []
            return []

        used_candidate_indexes: set[int] = set()
        next_pending_tracks: list[_LiveTrack] = []
        confirmed_tracks: list[_LiveTrack] = []

        for track in self.pending_tracks:
            match_index = _best_matching_detection_index(
                track.box,
                candidates,
                self.match_min_iou,
                used_candidate_indexes,
            )
            if match_index is None:
                continue

            used_candidate_indexes.add(match_index)
            self._update_track(track, candidates[match_index])
            if track.stable_frames >= self.confirm_frames:
                confirmed_tracks.append(track)
            else:
                next_pending_tracks.append(track)

        for index, candidate in enumerate(candidates):
            if index in used_candidate_indexes:
                continue
            candidate_box = _detection_box(candidate)
            if candidate_box is None:
                continue
            track = self._new_track(candidate, candidate_box)
            if track.stable_frames >= self.confirm_frames:
                confirmed_tracks.append(track)
            else:
                next_pending_tracks.append(track)

        self.pending_tracks = next_pending_tracks
        return confirmed_tracks

    def _update_track(self, track: _LiveTrack, detection: dict[str, Any]) -> None:
        matched_box = _detection_box(detection)
        assert matched_box is not None
        track.box = _smooth_box(track.box, matched_box, self.box_smoothing)
        track.detection = {**detection, "box": track.box}
        track.stable_frames += 1
        track.lost_frames = 0
        track.pending_switch_frames = 0

    def _new_track(self, detection: dict[str, Any], box: list[float]) -> _LiveTrack:
        track_id = f"live-jade-{self._next_track_number}"
        self._next_track_number += 1
        return _LiveTrack(track_id=track_id, box=list(box), detection={**detection, "box": list(box)})

    def _current_update(self, *, candidate_count: int) -> LiveYoloTrackingUpdate:
        detections = [self._track_detection(track) for track in self.active_tracks]
        if detections:
            status = "confirmed" if any(track.lost_frames == 0 for track in self.active_tracks) else "lost"
            return LiveYoloTrackingUpdate(
                detections=detections,
                tracking=self._tracking_status(status, confirmed=True, candidate_count=candidate_count),
            )
        if self.pending_tracks:
            return LiveYoloTrackingUpdate(
                detections=[],
                tracking=self._tracking_status("pending", confirmed=False, candidate_count=candidate_count),
            )
        return LiveYoloTrackingUpdate(
            detections=[],
            tracking=self._tracking_status("idle", confirmed=False, candidate_count=candidate_count),
        )

    def _track_detection(self, track: _LiveTrack) -> dict[str, Any]:
        status = "lost" if track.lost_frames > 0 else "confirmed"
        return {
            **track.detection,
            "box": [round(value, 2) for value in track.box],
            "track_id": track.track_id,
            "confirmed": True,
            "tracking_state": status,
            "stable_frames": track.stable_frames,
            "lost_frames": track.lost_frames,
        }

    def _tracking_status(self, status: str, *, confirmed: bool, candidate_count: int) -> dict[str, Any]:
        track = self.active or self.pending
        pending_switch_frames = 0
        if self.active_tracks and self.pending_tracks:
            pending_switch_frames = max(track.stable_frames for track in self.pending_tracks)
        return {
            "status": status,
            "confirmed": confirmed,
            "track_id": track.track_id if track else "",
            "stable_frames": track.stable_frames if track else 0,
            "lost_frames": track.lost_frames if track and track in self.active_tracks else 0,
            "pending_switch_frames": pending_switch_frames,
            "candidate_count": candidate_count,
            "active_count": len(self.active_tracks),
            "pending_count": len(self.pending_tracks),
            "confirm_frames": self.confirm_frames,
            "hold_frames": self.hold_frames,
            "switch_frames": self.switch_frames,
        }


_live_trackers: dict[str, LiveJadeTracker] = {}
_live_snapshot_states: dict[str, LiveYoloSnapshotState] = {}
_live_yolo_debug_logged_at: dict[str, float] = {}


@router.post("/sessions/{session_id}/jade-yolo/detect-frame")
async def detect_jade_yolo_frame(session_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    if session_id not in app_state.sessions:
        raise HTTPException(status_code=404, detail="直播会话不存在")

    content_type = (file.content_type or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图片帧")

    started_at = time.perf_counter()
    upload_dir = WORKSPACE_DIR / "uploads" / "yolo-live" / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = _safe_suffix(file.filename or "", content_type)
    image_path = upload_dir / f"{app_state.new_id('yolo-live')}{suffix}"

    try:
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="图片帧为空")
        image_path.write_bytes(data)
        save_ms = (time.perf_counter() - started_at) * 1000

        width, height = _image_size(image_path)
        snapshot = _maybe_save_live_snapshot(session_id, image_path, width=width, height=height)
        yolo_started_at = time.perf_counter()
        candidate_dicts, runtime = _detect_live_jade_candidates(
            image_path,
            width=width,
            height=height,
        )
        tracking = _tracker_for_session(session_id).update(candidate_dicts)
        yolo_ms = (time.perf_counter() - yolo_started_at) * 1000
        _log_live_yolo_debug(session_id, candidate_dicts, tracking, runtime)

        return {
            "status": "ok",
            "image_width": width,
            "image_height": height,
            "detections": tracking.detections,
            "candidates": candidate_dicts,
            "tracking": tracking.tracking,
            "runtime": runtime,
            "snapshot": snapshot,
            "live_min_confidence": LIVE_YOLO_MIN_CONFIDENCE,
            "live_roi": LIVE_YOLO_ROI,
            "live_confirm_frames": LIVE_YOLO_CONFIRM_FRAMES,
            "live_hold_frames": LIVE_YOLO_HOLD_FRAMES,
            "live_switch_frames": LIVE_YOLO_SWITCH_FRAMES,
            "timings": {
                "save_ms": round(save_ms, 2),
                "yolo_ms": round(yolo_ms, 2),
                "total_ms": round((time.perf_counter() - started_at) * 1000, 2),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"YOLO 实时检测失败：{str(exc)[:160]}") from exc
    finally:
        if not os.getenv("JLAO_KEEP_YOLO_LIVE_FRAMES", "").strip():
            try:
                image_path.unlink(missing_ok=True)
            except Exception:
                pass


def _detect_live_jade_candidates(
    image_path: Path,
    *,
    width: int,
    height: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    roi_box = _live_yolo_roi_box(width, height)
    detections, runtime = detect_jade_candidates(
        image_path,
        min_confidence=LIVE_YOLO_MIN_CONFIDENCE,
        max_detections=5,
    )
    detection_dicts = [item.to_dict() for item in detections]
    runtime = {
        **runtime,
        "live_roi": {
            "ratio": LIVE_YOLO_ROI,
            "box": list(roi_box),
            "filtered_from": len(detections),
            "mode": "full-frame",
        },
    }
    return detection_dicts, runtime


def _log_live_yolo_debug(
    session_id: str,
    candidates: list[dict[str, Any]],
    tracking: LiveYoloTrackingUpdate,
    runtime: dict[str, Any],
) -> None:
    now = time.monotonic()
    last_logged = _live_yolo_debug_logged_at.get(session_id, 0.0)
    if now - last_logged < 2.0:
        return
    _live_yolo_debug_logged_at[session_id] = now

    top = max(candidates, key=lambda item: float(item.get("confidence") or 0), default=None)
    top_label = str(top.get("label") or "none") if top else "none"
    top_conf = float(top.get("confidence") or 0) if top else 0.0
    print(
        f"[yolo-live {session_id}] candidates={len(candidates)} "
        f"top={top_label}:{top_conf:.3f} "
        f"tracking={tracking.tracking.get('status')} "
        f"confirmed={len(tracking.detections)} "
        f"min_conf={LIVE_YOLO_MIN_CONFIDENCE:.3f} "
        f"model={Path(str(runtime.get('model_path') or '')).name or runtime.get('reason') or 'unknown'}"
    )


def _maybe_save_live_snapshot(session_id: str, image_path: Path, *, width: int, height: int) -> dict[str, Any]:
    if not LIVE_YOLO_SNAPSHOT_ENABLED:
        return {"enabled": False, "saved": False, "reason": "disabled"}
    if LIVE_YOLO_SNAPSHOT_MAX_PER_SESSION <= 0:
        return {"enabled": True, "saved": False, "reason": "limit-disabled"}

    state = _live_snapshot_state_for_session(session_id)
    if state.saved >= LIVE_YOLO_SNAPSHOT_MAX_PER_SESSION:
        return {
            "enabled": True,
            "saved": False,
            "reason": "max-reached",
            "batch_id": state.batch_id,
            "count": state.saved,
            "limit": LIVE_YOLO_SNAPSHOT_MAX_PER_SESSION,
        }

    now = time.monotonic()
    if state.last_saved_at and now - state.last_saved_at < LIVE_YOLO_SNAPSHOT_INTERVAL_SECONDS:
        return {
            "enabled": True,
            "saved": False,
            "reason": "interval",
            "batch_id": state.batch_id,
            "count": state.saved,
            "limit": LIVE_YOLO_SNAPSHOT_MAX_PER_SESSION,
        }

    state.image_dir.mkdir(parents=True, exist_ok=True)
    state.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    LIVE_YOLO_FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)

    index = state.saved + 1
    target_path = state.image_dir / f"real_{index:04d}{image_path.suffix.lower() or '.jpg'}"
    target_path.write_bytes(image_path.read_bytes())
    image_ref = _public_upload_ref(target_path)
    feedback_id = f"jade-yolo-live-{uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()

    _append_snapshot_manifest(
        state.manifest_path,
        {
            "image": image_ref,
            "batch_id": state.batch_id,
            "feedback_id": feedback_id,
            "session_id": session_id,
            "source_frame_id": image_path.stem,
            "width": width,
            "height": height,
            "created_at": created_at,
        },
    )
    _append_feedback_record(
        {
            "id": feedback_id,
            "created_at": created_at,
            "input": {
                "image": image_ref,
                "batch_id": state.batch_id,
                "source": "yolo-live",
                "session_id": session_id,
                "source_frame_id": image_path.stem,
                "image_width": width,
                "image_height": height,
            },
            "predicted": {},
            "corrected": {"color": "", "water": "", "style": "", "theme": ""},
            "evidence": {"images": [image_ref], "texts": [], "detections": []},
            "confidence": 0.0,
            "source": "yolo-live-snapshot",
            "attribute_sources": {},
            "needs_review": True,
            "review_status": "pending",
            "review_reason": "needs-human-yolo-box",
            "training": {
                "suggested_classes": [],
                "yolo_ready": False,
                "requires_manual_box": True,
                "box_mode": "",
            },
        }
    )

    state.saved = index
    state.last_saved_at = now
    pet = _snapshot_pet(state.saved)
    print(
        f"[yolo-live-snapshot {session_id}]\n"
        f"{pet}\n"
        f"saved {state.saved}/{LIVE_YOLO_SNAPSHOT_MAX_PER_SESSION} "
        f"batch={state.batch_id} image={image_ref} feedback={feedback_id}"
    )
    return {
        "enabled": True,
        "saved": True,
        "batch_id": state.batch_id,
        "count": state.saved,
        "limit": LIVE_YOLO_SNAPSHOT_MAX_PER_SESSION,
        "image": image_ref,
        "feedback_id": feedback_id,
    }


def _snapshot_pet(saved_count: int) -> str:
    if not LIVE_YOLO_SNAPSHOT_PETS:
        return ""
    return LIVE_YOLO_SNAPSHOT_PETS[(max(1, saved_count) - 1) % len(LIVE_YOLO_SNAPSHOT_PETS)]


def _live_snapshot_state_for_session(session_id: str) -> LiveYoloSnapshotState:
    state = _live_snapshot_states.get(session_id)
    if state is not None:
        return state
    safe_session_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in session_id).strip("-")
    safe_session_id = safe_session_id or "session"
    batch_id = f"yolo-live-{safe_session_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    batch_dir = LIVE_YOLO_SNAPSHOT_ROOT / batch_id
    state = LiveYoloSnapshotState(
        batch_id=batch_id,
        image_dir=batch_dir / "images",
        manifest_path=batch_dir / "manifest.csv",
    )
    _live_snapshot_states[session_id] = state
    return state


def _append_snapshot_manifest(path: Path, row: dict[str, Any]) -> None:
    needs_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LIVE_YOLO_SNAPSHOT_MANIFEST_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in LIVE_YOLO_SNAPSHOT_MANIFEST_FIELDS})


def _append_feedback_record(record: dict[str, Any]) -> None:
    with LIVE_YOLO_FEEDBACK_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _public_upload_ref(path: Path) -> str:
    try:
        relative = path.resolve().relative_to((WORKSPACE_DIR / "uploads").resolve())
        return "/uploads/" + str(relative).replace("\\", "/")
    except ValueError:
        return str(path)


def _tracker_for_session(session_id: str) -> LiveJadeTracker:
    now = time.monotonic()
    stale_ids = [
        key for key, tracker in _live_trackers.items()
        if now - tracker.updated_at > LIVE_TRACKER_IDLE_TTL_SECONDS
    ]
    for key in stale_ids:
        _live_trackers.pop(key, None)

    tracker = _live_trackers.get(session_id)
    if tracker is None:
        tracker = LiveJadeTracker()
        _live_trackers[session_id] = tracker
    return tracker


def _detection_box(detection: dict[str, Any]) -> list[float] | None:
    box = detection.get("box")
    if not isinstance(box, list) or len(box) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(value) for value in box]
    except (TypeError, ValueError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]


def _best_matching_detection(
    track_box: list[float],
    candidates: list[dict[str, Any]],
    min_iou: float,
) -> dict[str, Any] | None:
    match_index = _best_matching_detection_index(track_box, candidates, min_iou)
    return candidates[match_index] if match_index is not None else None


def _best_matching_detection_index(
    track_box: list[float],
    candidates: list[dict[str, Any]],
    min_iou: float,
    used_indexes: set[int] | None = None,
) -> int | None:
    used = used_indexes or set()
    best: tuple[float, int] | None = None
    for index, candidate in enumerate(candidates):
        if index in used:
            continue
        candidate_box = _detection_box(candidate)
        if candidate_box is None:
            continue
        iou = _box_iou(track_box, candidate_box)
        center_match = _center_distance(track_box, candidate_box) <= _max_center_distance(track_box, candidate_box)
        if iou < min_iou and not center_match:
            continue
        confidence = float(candidate.get("confidence") or 0.0)
        score = iou * 10.0 + confidence
        if best is None or score > best[0]:
            best = (score, index)
    return best[1] if best else None


def _smooth_box(previous: list[float], current: list[float], smoothing: float) -> list[float]:
    keep = max(0.0, min(0.95, smoothing))
    take = 1.0 - keep
    return [round(previous[index] * keep + current[index] * take, 2) for index in range(4)]


def _box_iou(first: list[float], second: list[float]) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[2], second[2])
    bottom = min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    if intersection <= 0:
        return 0.0
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def _center_distance(first: list[float], second: list[float]) -> float:
    first_center = ((first[0] + first[2]) / 2.0, (first[1] + first[3]) / 2.0)
    second_center = ((second[0] + second[2]) / 2.0, (second[1] + second[3]) / 2.0)
    return ((first_center[0] - second_center[0]) ** 2 + (first_center[1] - second_center[1]) ** 2) ** 0.5


def _max_center_distance(first: list[float], second: list[float]) -> float:
    first_diag = ((first[2] - first[0]) ** 2 + (first[3] - first[1]) ** 2) ** 0.5
    second_diag = ((second[2] - second[0]) ** 2 + (second[3] - second[1]) ** 2) ** 0.5
    return max(60.0, (first_diag + second_diag) * 0.35)


def _live_yolo_roi_box(width: int, height: int) -> tuple[int, int, int, int]:
    left_ratio, top_ratio, right_ratio, bottom_ratio = LIVE_YOLO_ROI
    left = max(0, min(width - 1, int(width * left_ratio)))
    top = max(0, min(height - 1, int(height * top_ratio)))
    right = max(left + 1, min(width, int(width * right_ratio)))
    bottom = max(top + 1, min(height, int(height * bottom_ratio)))
    return left, top, right, bottom


def _safe_suffix(filename: str, content_type: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    return ".jpg"


def _image_size(image_path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow 未安装，无法读取图片尺寸") from exc

    with Image.open(image_path) as image:
        return int(image.width), int(image.height)
