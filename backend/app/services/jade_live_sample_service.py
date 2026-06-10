from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas import FrameSnapshot
from app.services.jade_feedback_learning_service import clean_attribute_value
from app.services.jade_multimodal_service import JadeAnalysis
from app.services.jade_training_service import class_names_from_feedback


WORKSPACE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_FEEDBACK_PATH = WORKSPACE_DIR / "data" / "jade_feedback.jsonl"
MIN_LIVE_SAMPLE_CONFIDENCE = 0.0
MIN_SECONDS_BETWEEN_SAME_SAMPLE = 12.0
RELIABLE_WEAK_CLASS_SOURCES = {
    "feedback-learning",
    "live-frame-correction",
    "speech",
    "yolo",
    "local-vlm",
}
RELIABLE_WEAK_ATTRIBUTE_SOURCES = {
    "feedback-learning",
    "live-frame-correction",
    "speech",
    "yolo",
    "local-vlm",
    "opencv",
}

_last_sample_at: dict[str, datetime] = {}


def record_live_jade_weak_sample(
    *,
    session_id: str,
    image_url: str,
    analysis: JadeAnalysis,
    feedback_path: Path = DEFAULT_FEEDBACK_PATH,
) -> dict[str, Any]:
    if not image_url or analysis.confidence < MIN_LIVE_SAMPLE_CONFIDENCE:
        return {"status": "skipped", "reason": "low-confidence-or-missing-image"}
    if not any([analysis.color, analysis.water, analysis.style, analysis.theme]):
        return {"status": "skipped", "reason": "missing-jade-attributes"}
    quality = weak_sample_quality(analysis)
    if not quality["recordable"]:
        return {"status": "skipped", "reason": "weak-attribute-source-not-recordable", "quality": quality}

    sample_key = live_sample_key(session_id, analysis)
    now = datetime.now(timezone.utc)
    previous = _last_sample_at.get(sample_key)
    if previous and (now - previous).total_seconds() < MIN_SECONDS_BETWEEN_SAME_SAMPLE:
        return {"status": "skipped", "reason": "rate-limited", "sample_key": sample_key}
    _last_sample_at[sample_key] = now

    attributes = {
        "color": analysis.color,
        "water": analysis.water,
        "style": analysis.style,
        "theme": analysis.theme,
    }
    suggested_classes = class_names_from_feedback({"corrected": attributes})
    review_reason = "verify-weak-label"
    if not suggested_classes:
        review_reason = "missing-style-theme"
    elif not quality["class_reliable"]:
        review_reason = "verify-class-source"
    record = {
        "id": f"live-weak-{session_id}-{int(now.timestamp() * 1000)}",
        "created_at": now.isoformat(),
        "input": {
            "image": image_url,
            "text": "\n".join(analysis.evidence_texts[-6:]),
        },
        "predicted": attributes,
        "corrected": attributes,
        "evidence": {
            "images": [image_url],
            "texts": analysis.evidence_texts,
            "detections": analysis.detections,
        },
        "confidence": round(analysis.confidence, 3),
        "source": "live-frame-weak-label",
        "needs_review": True,
        "review_reason": review_reason,
        "quality": quality,
        "training": {
            "suggested_classes": suggested_classes,
            "yolo_ready": bool(suggested_classes),
            "requires_manual_box": True,
        },
        "signals": analysis.signals,
    }
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    with feedback_path.open("a", encoding="utf-8") as feedback_file:
        feedback_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"status": "ok", "id": record["id"], "sample_key": sample_key}


def weak_sample_quality(analysis: JadeAnalysis) -> dict[str, Any]:
    sources = (analysis.signals or {}).get("attribute_sources") or {}
    attribute_sources: dict[str, Any] = {}
    class_sources: dict[str, Any] = {}
    class_reliable = False
    attribute_reliable = False
    for key in ["color", "water", "style", "theme"]:
        if not getattr(analysis, key, ""):
            continue
        source = sources.get(key) if isinstance(sources, dict) else {}
        if not isinstance(source, dict):
            source = {}
        source_name = str(source.get("source") or "")
        method = str(source.get("method") or "")
        source_payload = {
            "source": source_name,
            "method": method,
            "value": getattr(analysis, key, ""),
        }
        attribute_sources[key] = source_payload
        if source_name in RELIABLE_WEAK_ATTRIBUTE_SOURCES:
            attribute_reliable = True
        if key in {"style", "theme"}:
            class_sources[key] = source_payload
            if source_name in RELIABLE_WEAK_CLASS_SOURCES:
                class_reliable = True
    recordable = bool(attribute_sources) and (attribute_reliable or analysis.confidence >= 0.5)
    return {
        "reliable": class_reliable,
        "recordable": recordable,
        "class_reliable": class_reliable,
        "attribute_reliable": attribute_reliable,
        "attribute_sources": attribute_sources,
        "class_sources": class_sources,
        "confidence": round(analysis.confidence, 3),
    }


def live_sample_key(session_id: str, analysis: JadeAnalysis) -> str:
    parts = [
        session_id,
        analysis.color or "-",
        analysis.water or "-",
        analysis.style or "-",
        analysis.theme or "-",
    ]
    return "|".join(parts)


def record_frame_jade_correction(
    *,
    frame: FrameSnapshot,
    corrected: dict[str, Any],
    feedback_path: Path = DEFAULT_FEEDBACK_PATH,
) -> dict[str, Any]:
    cleaned = {
        key: clean_attribute_value(key, corrected.get(key))
        for key in ["color", "water", "style", "theme"]
    }
    if not any(cleaned.values()):
        return {"status": "skipped", "reason": "empty-correction"}

    predicted = {
        "color": frame.jade_color,
        "water": frame.jade_water,
        "style": frame.jade_style,
        "theme": frame.jade_theme,
    }
    now = datetime.now(timezone.utc)
    record = {
        "id": f"live-correction-{frame.id}-{int(now.timestamp() * 1000)}",
        "created_at": now.isoformat(),
        "input": {
            "image": frame.image_path,
            "text": "",
        },
        "predicted": predicted,
        "corrected": {
            key: value or predicted.get(key, "")
            for key, value in cleaned.items()
        },
        "evidence": {
            "images": [frame.image_path],
            "texts": [],
            "detections": frame.jade_detections,
        },
        "confidence": frame.jade_confidence,
        "source": "live-frame-correction",
        "needs_review": False,
        "review_status": "approved",
        "training": {
            "suggested_classes": class_names_from_feedback({"corrected": {
                key: value or predicted.get(key, "")
                for key, value in cleaned.items()
            }}),
            "yolo_ready": bool(class_names_from_feedback({"corrected": {
                key: value or predicted.get(key, "")
                for key, value in cleaned.items()
            }})),
            "requires_manual_box": True,
        },
        "signals": {
            "frame_id": frame.id,
            "attribute_sources": frame.jade_attribute_sources,
        },
    }
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    with feedback_path.open("a", encoding="utf-8") as feedback_file:
        feedback_file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"status": "ok", "id": record["id"]}
