from __future__ import annotations

from typing import Any


def feedback_record_batch_id(record: dict[str, Any]) -> str:
    input_payload = _as_dict(record.get("input"))
    batch_id = _clean(input_payload.get("batch_id"))
    if batch_id:
        return batch_id
    evidence = _as_dict(record.get("evidence"))
    texts = evidence.get("texts") if isinstance(evidence.get("texts"), list) else []
    for item in texts:
        text = _clean(item)
        if text.startswith("batch_id="):
            return text.split("=", 1)[1].strip()
    return ""


def feedback_record_matches_batch(record: dict[str, Any], batch_id: str) -> bool:
    cleaned = _clean(batch_id)
    if not cleaned:
        return False
    if feedback_record_batch_id(record) == cleaned:
        return True
    marker = f"batch_id={cleaned}"
    evidence = _as_dict(record.get("evidence"))
    texts = evidence.get("texts") if isinstance(evidence.get("texts"), list) else []
    return any(marker == _clean(text) or marker in _clean(text) for text in texts)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
