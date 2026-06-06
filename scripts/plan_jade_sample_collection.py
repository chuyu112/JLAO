from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_multimodal_service import JADE_COLORS, JADE_STYLES, JADE_THEMES, JADE_WATERS  # noqa: E402
from app.services.jade_training_config import JADE_YOLO_CLASS_NAMES  # noqa: E402
from app.services.jade_training_service import CLASS_TO_ID, class_names_from_feedback  # noqa: E402


ATTRIBUTE_KEYS = ["color", "water", "style", "theme"]
ATTRIBUTE_CATALOGS = {
    "color": JADE_COLORS,
    "water": JADE_WATERS,
    "style": JADE_STYLES,
    "theme": JADE_THEMES,
}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan jade sample collection gaps from a manifest.")
    parser.add_argument("--manifest", required=True, type=Path, help="CSV, JSON, or JSONL jade sample manifest.")
    parser.add_argument("--target-per-class", type=int, default=20)
    parser.add_argument("--target-per-color", type=int, default=10)
    parser.add_argument("--target-per-water", type=int, default=10)
    parser.add_argument("--target-per-style", type=int, default=20)
    parser.add_argument("--target-per-theme", type=int, default=10)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    manifest = resolve_path(args.manifest)
    if not manifest.exists():
        print(json.dumps({"status": "missing-manifest", "manifest": str(manifest)}, ensure_ascii=False))
        return 2

    rows = load_manifest_rows(manifest)
    class_counts: Counter[str] = Counter()
    attribute_counts: dict[str, Counter[str]] = {key: Counter() for key in ATTRIBUTE_KEYS}
    unknown_classes: Counter[str] = Counter()
    rows_without_class = 0

    for row in rows:
        attrs = {key: canonical_attribute(key, row.get(key)) for key in ATTRIBUTE_KEYS}
        for key, value in attrs.items():
            if value:
                attribute_counts[key][value] += 1
        classes = row_classes(row, attrs)
        if not classes:
            rows_without_class += 1
        for class_name in classes:
            if class_name in CLASS_TO_ID:
                class_counts[class_name] += 1
            else:
                unknown_classes[class_name] += 1

    payload = {
        "status": "ok",
        "manifest": str(manifest),
        "rows": len(rows),
        "rows_without_class": rows_without_class,
        "unknown_classes": dict(unknown_classes),
        "class_counts": ordered_counts(JADE_YOLO_CLASS_NAMES, class_counts),
        "class_deficits": deficits(JADE_YOLO_CLASS_NAMES, class_counts, args.target_per_class),
        "attribute_counts": {
            key: ordered_counts(sorted(catalog.keys()), attribute_counts[key])
            for key, catalog in ATTRIBUTE_CATALOGS.items()
        },
        "attribute_deficits": {
            "color": deficits(sorted(JADE_COLORS.keys()), attribute_counts["color"], args.target_per_color),
            "water": deficits(sorted(JADE_WATERS.keys()), attribute_counts["water"], args.target_per_water),
            "style": deficits(sorted(JADE_STYLES.keys()), attribute_counts["style"], args.target_per_style),
            "theme": deficits(sorted(JADE_THEMES.keys()), attribute_counts["theme"], args.target_per_theme),
        },
        "targets": {
            "per_class": args.target_per_class,
            "per_color": args.target_per_color,
            "per_water": args.target_per_water,
            "per_style": args.target_per_style,
            "per_theme": args.target_per_theme,
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_manifest_rows(manifest: Path) -> list[dict[str, Any]]:
    suffix = manifest.suffix.lower()
    if suffix == ".csv":
        with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    if suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        with manifest.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                text = line.strip()
                if text:
                    rows.append(json.loads(text))
        return rows
    with manifest.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        samples = payload.get("samples") or payload.get("records") or []
        return samples if isinstance(samples, list) else []
    return payload if isinstance(payload, list) else []


def row_classes(row: dict[str, Any], attrs: dict[str, str]) -> list[str]:
    explicit = parse_explicit_classes(row)
    inferred = class_names_from_feedback(
        {
            "corrected": {
                "style": attrs.get("style", ""),
                "theme": attrs.get("theme", ""),
            },
            "training": {
                "suggested_classes": [class_name for class_name in explicit if class_name in CLASS_TO_ID],
            },
        }
    )
    result = list(explicit)
    for class_name in inferred:
        if class_name not in result:
            result.append(class_name)
    return result


def parse_explicit_classes(row: dict[str, Any]) -> list[str]:
    raw = clean(row.get("class_name") or row.get("class") or row.get("yolo_class") or row.get("class_names"))
    result: list[str] = []
    for item in raw.replace(";", ",").replace("|", ",").split(","):
        class_name = item.strip()
        if class_name and class_name not in result:
            result.append(class_name)
    return result


def canonical_attribute(key: str, value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    catalog = ATTRIBUTE_CATALOGS.get(key, {})
    if text in catalog:
        return text
    for canonical, aliases in catalog.items():
        if any(alias and alias in text for alias in aliases):
            return canonical
    return text


def ordered_counts(keys: list[str], counts: Counter[str]) -> dict[str, int]:
    return {key: int(counts.get(key, 0)) for key in keys}


def deficits(keys: list[str], counts: Counter[str], target: int) -> dict[str, int]:
    return {
        key: max(0, int(target) - int(counts.get(key, 0)))
        for key in keys
        if int(counts.get(key, 0)) < int(target)
    }


def clean(value: Any) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
