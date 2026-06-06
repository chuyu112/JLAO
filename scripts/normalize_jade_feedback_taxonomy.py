from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_feedback_learning_service import clean_attribute_value  # noqa: E402
from app.services.jade_training_service import DEFAULT_FEEDBACK_PATH  # noqa: E402


ATTRIBUTES = ("color", "water", "style", "theme")


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize old jade feedback taxonomy labels without changing images or boxes.")
    parser.add_argument("--feedback", type=Path, default=DEFAULT_FEEDBACK_PATH)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "jade_feedback.normalized.jsonl")
    parser.add_argument("--in-place", action="store_true", help="Overwrite --feedback via a temporary file.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    feedback_path = resolve_path(args.feedback)
    if not feedback_path.exists():
        print(json.dumps({"status": "missing-feedback", "feedback": str(feedback_path)}, ensure_ascii=False))
        return 2

    records = load_jsonl(feedback_path)
    normalized_records: list[dict[str, Any]] = []
    changed = 0
    changes: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        normalized, row_changes = normalize_record(record)
        normalized_records.append(normalized)
        if row_changes:
            changed += 1
            changes.append({"index": index, "id": str(record.get("id") or ""), "changes": row_changes})

    output_path = feedback_path if args.in_place else resolve_path(args.output)
    write_jsonl_atomic(output_path, normalized_records)
    payload = {
        "status": "ok",
        "feedback": str(feedback_path),
        "output": str(output_path),
        "in_place": bool(args.in_place),
        "records": len(records),
        "changed_records": changed,
        "changes": changes[:100],
        "truncated_changes": max(0, len(changes) - 100),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def normalize_record(record: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    result = json.loads(json.dumps(record, ensure_ascii=False))
    changes: list[dict[str, str]] = []

    for section_name in ("corrected", "predicted"):
        section = result.get(section_name)
        if not isinstance(section, dict):
            continue
        original_style = str(section.get("style") or "").strip()
        original_theme = str(section.get("theme") or "").strip()
        for key in ATTRIBUTES:
            before = str(section.get(key) or "").strip()
            after = clean_attribute_value(key, before)
            if after != before:
                section[key] = after
                changes.append({"section": section_name, "attribute": key, "from": before, "to": after})
        implied_theme = theme_from_old_style(original_style)
        if implied_theme and not original_theme and not str(section.get("theme") or "").strip():
            section["theme"] = implied_theme
            changes.append({"section": section_name, "attribute": "theme", "from": "", "to": implied_theme})

    sources = result.get("attribute_sources")
    if isinstance(sources, dict):
        for key in ATTRIBUTES:
            source = sources.get(key)
            if not isinstance(source, dict):
                continue
            before = str(source.get("value") or "").strip()
            after = clean_attribute_value(key, before)
            if after != before:
                source["value"] = after
                changes.append({"section": "attribute_sources", "attribute": key, "from": before, "to": after})

    return result, changes


def theme_from_old_style(value: str) -> str:
    compact = value.replace(" ", "").replace("·", "").replace("/", "")
    return {
        "龙牌": "龙",
        "山水牌": "山水",
        "无事牌": "无事牌",
        "平安无事牌": "无事牌",
        "观音": "观音",
        "佛公": "佛公",
        "叶子": "叶子",
        "如意": "如意",
        "葫芦": "葫芦",
        "福瓜": "福瓜",
        "貔貅": "貔貅",
    }.get(compact, "")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        value = json.loads(stripped)
        if isinstance(value, dict):
            records.append(value)
    return records


def write_jsonl_atomic(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    temp_path.replace(path)


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


if __name__ == "__main__":
    raise SystemExit(main())
