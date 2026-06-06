from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.jade_yolo_service import DEFAULT_YOLO_MIN_CONFIDENCE, detect_jade_candidates
from app.state import WORKSPACE_DIR, app_state


router = APIRouter()
LIVE_YOLO_MIN_CONFIDENCE = DEFAULT_YOLO_MIN_CONFIDENCE
LIVE_YOLO_ROI = (0.0, 0.12, 0.92, 0.84)
LIVE_YOLO_CONFIRM_FRAMES = 3
LIVE_YOLO_HOLD_FRAMES = 10
LIVE_YOLO_SWITCH_FRAMES = 8
LIVE_YOLO_MATCH_MIN_IOU = 0.12
LIVE_YOLO_BOX_SMOOTHING = 0.65
LIVE_TRACKER_IDLE_TTL_SECONDS = 600


@dataclass
class LiveYoloTrackingUpdate:
    detections: list[dict[str, Any]]
    tracking: dict[str, Any]


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
        yolo_started_at = time.perf_counter()
        candidate_dicts, runtime = _detect_live_jade_candidates(
            image_path,
            width=width,
            height=height,
        )
        tracking = _tracker_for_session(session_id).update(candidate_dicts)
        yolo_ms = (time.perf_counter() - yolo_started_at) * 1000

        return {
            "status": "ok",
            "image_width": width,
            "image_height": height,
            "detections": tracking.detections,
            "candidates": candidate_dicts,
            "tracking": tracking.tracking,
            "runtime": runtime,
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
    crop_path = image_path.with_name(f"{image_path.stem}-roi{image_path.suffix}")
    try:
        _crop_image(image_path, crop_path, roi_box)
        detections, runtime = detect_jade_candidates(
            crop_path,
            min_confidence=LIVE_YOLO_MIN_CONFIDENCE,
            max_detections=3,
        )
        offset_x, offset_y, _, _ = roi_box
        detection_dicts = [
            _remap_live_detection(item.to_dict(), offset_x=offset_x, offset_y=offset_y)
            for item in detections
        ]
        runtime = {
            **runtime,
            "live_roi": {
                "ratio": LIVE_YOLO_ROI,
                "box": list(roi_box),
                "filtered_from": len(detections),
            },
        }
        return detection_dicts, runtime
    finally:
        try:
            crop_path.unlink(missing_ok=True)
        except Exception:
            pass


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


def _crop_image(image_path: Path, crop_path: Path, roi_box: tuple[int, int, int, int]) -> None:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow 未安装，无法裁剪 YOLO 实时画面") from exc

    with Image.open(image_path) as image:
        image.crop(roi_box).save(crop_path, quality=92)


def _remap_live_detection(
    detection: dict[str, Any],
    *,
    offset_x: int,
    offset_y: int,
) -> dict[str, Any]:
    box = detection.get("box")
    if not isinstance(box, list) or len(box) != 4:
        return detection
    remapped = [
        round(float(box[0]) + offset_x, 2),
        round(float(box[1]) + offset_y, 2),
        round(float(box[2]) + offset_x, 2),
        round(float(box[3]) + offset_y, 2),
    ]
    return {**detection, "box": remapped}


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
