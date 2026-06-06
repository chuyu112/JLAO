from __future__ import annotations

from typing import Any


CORE_ATTRIBUTES = ["color", "water", "style", "theme"]
LOW_CONFIDENCE_THRESHOLD = 0.45


def jade_analysis_review_flags(analysis: Any) -> list[str]:
    flags: list[str] = []
    if _float(getattr(analysis, "confidence", 0.0)) < LOW_CONFIDENCE_THRESHOLD:
        flags.append("low-confidence")

    missing = [
        key
        for key in CORE_ATTRIBUTES
        if not str(getattr(analysis, key, "") or "").strip()
    ]
    if missing:
        flags.append("missing-" + "|".join(missing))

    detections = getattr(analysis, "detections", None)
    if not detections:
        flags.append("no-yolo-detections")

    signals = getattr(analysis, "signals", None)
    attribute_sources = signals.get("attribute_sources") if isinstance(signals, dict) else None
    if not isinstance(attribute_sources, dict) or not attribute_sources:
        flags.append("no-attribute-sources")

    return flags


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
