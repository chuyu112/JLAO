import inspect
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api import jade_yolo_live
from app.services.jade_yolo_service import DEFAULT_YOLO_MIN_CONFIDENCE


def test_live_yolo_filters_unreliable_stream_noise():
    assert jade_yolo_live.LIVE_YOLO_MIN_CONFIDENCE == DEFAULT_YOLO_MIN_CONFIDENCE
    assert jade_yolo_live.LIVE_YOLO_MIN_CONFIDENCE == 0.15

    source = inspect.getsource(jade_yolo_live._detect_live_jade_candidates)
    assert "min_confidence=LIVE_YOLO_MIN_CONFIDENCE" in source


def test_live_yolo_detects_in_subject_roi_and_remaps_boxes():
    assert jade_yolo_live.LIVE_YOLO_ROI == (0.0, 0.12, 0.92, 0.84)

    assert jade_yolo_live._live_yolo_roi_box(461, 1024) == (0, 122, 424, 860)

    detection = jade_yolo_live._remap_live_detection(
        {"label": "jade", "confidence": 0.12, "box": [10, 20, 110, 220]},
        offset_x=0,
        offset_y=122,
    )
    assert detection["box"] == [10, 142, 110, 342]

    source = inspect.getsource(jade_yolo_live.detect_jade_yolo_frame)
    assert "_detect_live_jade_candidates" in source


def test_live_yolo_tracker_requires_stable_frames_before_confirming():
    tracker = jade_yolo_live.LiveJadeTracker(confirm_frames=3)
    candidate = {"label": "jade", "confidence": 0.05, "box": [100, 200, 220, 360]}

    first = tracker.update([candidate])
    assert first.detections == []
    assert first.tracking["status"] == "pending"
    assert first.tracking["confirmed"] is False
    assert first.tracking["stable_frames"] == 1

    second = tracker.update([{**candidate, "box": [104, 204, 224, 364]}])
    assert second.detections == []
    assert second.tracking["status"] == "pending"
    assert second.tracking["stable_frames"] == 2

    third = tracker.update([{**candidate, "box": [108, 208, 228, 368]}])
    assert len(third.detections) == 1
    assert third.tracking["status"] == "confirmed"
    assert third.tracking["confirmed"] is True
    assert third.tracking["track_id"] == third.detections[0]["track_id"]
    assert third.detections[0]["confirmed"] is True


def test_live_yolo_tracker_confirms_multiple_separate_jades():
    tracker = jade_yolo_live.LiveJadeTracker(confirm_frames=2, switch_frames=4, hold_frames=4)
    left = {"label": "jade", "confidence": 0.72, "box": [80, 180, 180, 330]}
    right = {"label": "jade", "confidence": 0.68, "box": [280, 190, 390, 345]}

    first = tracker.update([left, right])
    assert first.detections == []
    assert first.tracking["status"] == "pending"
    assert first.tracking["pending_count"] == 2

    confirmed = tracker.update(
        [
            {**left, "box": [84, 184, 184, 334]},
            {**right, "box": [284, 194, 394, 349]},
        ]
    )

    assert len(confirmed.detections) == 2
    assert confirmed.tracking["status"] == "confirmed"
    assert confirmed.tracking["active_count"] == 2
    assert {item["track_id"] for item in confirmed.detections} == {"live-jade-1", "live-jade-2"}
    assert all(item["confirmed"] is True for item in confirmed.detections)


def test_live_yolo_tracker_prefers_active_track_over_higher_confidence_distractor():
    tracker = jade_yolo_live.LiveJadeTracker(confirm_frames=2, switch_frames=4, hold_frames=4)
    original = {"label": "jade", "confidence": 0.04, "box": [100, 200, 220, 360]}

    tracker.update([original])
    confirmed = tracker.update([{**original, "box": [102, 202, 222, 362]}])
    track_id = confirmed.detections[0]["track_id"]

    update = tracker.update(
        [
            {"label": "jade", "confidence": 0.02, "box": [106, 206, 226, 366]},
            {"label": "jade", "confidence": 0.20, "box": [20, 650, 150, 820]},
        ]
    )

    assert len(update.detections) == 1
    assert update.detections[0]["track_id"] == track_id
    assert update.detections[0]["box"][0] > 95
    assert update.detections[0]["box"][1] < 230
    assert update.tracking["status"] == "confirmed"


def test_live_yolo_tracker_holds_track_instead_of_jumping_to_unstable_new_candidate():
    tracker = jade_yolo_live.LiveJadeTracker(confirm_frames=2, switch_frames=4, hold_frames=4)
    original = {"label": "jade", "confidence": 0.04, "box": [100, 200, 220, 360]}

    tracker.update([original])
    confirmed = tracker.update([{**original, "box": [101, 201, 221, 361]}])
    track_id = confirmed.detections[0]["track_id"]
    held_box = confirmed.detections[0]["box"]

    jumped = tracker.update([{"label": "jade", "confidence": 0.25, "box": [300, 620, 430, 850]}])

    assert len(jumped.detections) == 1
    assert jumped.detections[0]["track_id"] == track_id
    assert jumped.detections[0]["tracking_state"] == "lost"
    assert jumped.detections[0]["box"] == held_box
    assert jumped.tracking["pending_switch_frames"] == 1
