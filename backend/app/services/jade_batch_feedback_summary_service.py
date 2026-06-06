from __future__ import annotations

from typing import Any


ATTRIBUTES = ["color", "water", "style", "theme"]
MINIMUM_YOLO_READY_RECORDS = 12


def summarize_jade_batch_feedback(records: list[dict[str, Any]]) -> dict[str, Any]:
    attribute_counts = {key: 0 for key in ATTRIBUTES}
    training_counts = {
        "yolo_ready": 0,
        "requires_manual_box": 0,
        "whole_image_box": 0,
        "manual_box": 0,
    }
    source_counts: dict[str, int] = {}
    for record in records:
        corrected = _as_dict(record.get("corrected"))
        training = _as_dict(record.get("training"))
        source = str(record.get("source") or "unknown").strip() or "unknown"
        source_counts[source] = source_counts.get(source, 0) + 1
        for key in attribute_counts:
            if str(corrected.get(key) or "").strip():
                attribute_counts[key] += 1
        if bool(training.get("yolo_ready")):
            training_counts["yolo_ready"] += 1
        if bool(training.get("requires_manual_box")):
            training_counts["requires_manual_box"] += 1
        box_mode = str(training.get("box_mode") or "").strip()
        if box_mode == "whole-image":
            training_counts["whole_image_box"] += 1
        if box_mode == "manual-box":
            training_counts["manual_box"] += 1
    return {
        "attribute_counts": attribute_counts,
        "training_counts": training_counts,
        "source_counts": source_counts,
        "readiness": jade_batch_feedback_readiness(
            record_count=len(records),
            attribute_counts=attribute_counts,
            training_counts=training_counts,
        ),
    }


def jade_batch_feedback_readiness(
    *,
    record_count: int,
    attribute_counts: dict[str, int],
    training_counts: dict[str, int],
) -> dict[str, Any]:
    blocking_reasons: list[str] = []
    recommended_next_steps: list[str] = []
    yolo_ready = int(training_counts.get("yolo_ready") or 0)
    requires_manual_box = int(training_counts.get("requires_manual_box") or 0)

    if record_count <= 0:
        blocking_reasons.append("no-feedback-records")
        recommended_next_steps.append("save-corrected-feedback-for-this-batch")
    if yolo_ready < MINIMUM_YOLO_READY_RECORDS:
        blocking_reasons.append("not-enough-yolo-ready-records")
        recommended_next_steps.append(f"collect-or-approve-at-least-{MINIMUM_YOLO_READY_RECORDS}-yolo-ready-records")
    if requires_manual_box > 0:
        blocking_reasons.append("manual-boxes-required")
        recommended_next_steps.append("add-manual-yolo-boxes-before-training")

    missing_attributes = [key for key, count in attribute_counts.items() if int(count or 0) <= 0]
    if missing_attributes:
        blocking_reasons.append("missing-attribute-coverage-" + "|".join(missing_attributes))
        recommended_next_steps.append("complete-corrected-color-water-style-theme-labels")

    if not recommended_next_steps:
        recommended_next_steps.append("run-train-batch-feedback")

    return {
        "can_try_batch_training": not blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "recommended_next_steps": recommended_next_steps,
        "minimum_yolo_ready_records": MINIMUM_YOLO_READY_RECORDS,
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
