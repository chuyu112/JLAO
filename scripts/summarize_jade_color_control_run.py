from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize jade color-control quality and prediction results.")
    parser.add_argument("--score", type=Path, default=ROOT / "tmp" / "jade-color-control-score.csv")
    parser.add_argument("--quality", type=Path, default=ROOT / "tmp" / "jade-color-control-quality.csv")
    parser.add_argument("--output-json", type=Path, default=ROOT / "tmp" / "jade-color-control-diagnosis.json")
    parser.add_argument("--output-csv", type=Path, default=ROOT / "tmp" / "jade-color-control-diagnosis.csv")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    score_path = resolve_path(args.score)
    quality_path = resolve_path(args.quality)
    score_rows = read_csv(score_path)
    quality_by_name = {filename_key(row.get("image") or row.get("filename")): row for row in read_csv(quality_path)}

    diagnosis_rows = []
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    by_expected_color: dict[str, Counter[str]] = defaultdict(Counter)
    by_expected_family: dict[str, Counter[str]] = defaultdict(Counter)
    quality_flags = Counter()
    confusions: dict[str, Counter[str]] = defaultdict(Counter)

    for row in score_rows:
        filename = clean(row.get("filename"))
        quality = quality_by_name.get(filename_key(filename), {})
        flags = split_flags(quality.get("flags"))
        for flag in flags:
            quality_flags[flag] += 1

        color_hit = is_hit(row.get("hit_color"))
        family_hit = is_hit(row.get("hit_color_family"))
        detail_hit = is_hit(row.get("hit_color_detail"))
        pattern_hit = is_hit(row.get("hit_color_pattern"))
        water_hit = is_hit(row.get("hit_water"))
        style_hit = is_hit(row.get("hit_style"))
        theme_hit = is_hit(row.get("hit_theme"))

        failure_bucket = classify_failure(
            flags=flags,
            color_hit=color_hit,
            family_hit=family_hit,
            detail_hit=detail_hit,
            pattern_hit=pattern_hit,
        )

        expected_color = clean(row.get("expected_color"))
        expected_family = clean(row.get("expected_color_family"))
        by_expected_color[expected_color][failure_bucket] += 1
        by_expected_family[expected_family][failure_bucket] += 1

        add_confusion(confusions["color"], row.get("expected_color"), row.get("predicted_color"), color_hit)
        add_confusion(confusions["color_family"], row.get("expected_color_family"), row.get("predicted_color_family"), family_hit)
        add_confusion(confusions["color_detail"], row.get("expected_color_detail"), row.get("predicted_color_detail"), detail_hit)
        add_confusion(confusions["color_pattern"], row.get("expected_color_pattern"), row.get("predicted_color_pattern"), pattern_hit)
        add_confusion(confusions["water"], row.get("expected_water"), row.get("predicted_water"), water_hit)
        add_confusion(confusions["style"], row.get("expected_style"), row.get("predicted_style"), style_hit)
        add_confusion(confusions["theme"], row.get("expected_theme"), row.get("predicted_theme"), theme_hit)

        for key, hit in {
            "color": color_hit,
            "color_family": family_hit,
            "color_detail": detail_hit,
            "color_pattern": pattern_hit,
            "water": water_hit,
            "style": style_hit,
            "theme": theme_hit,
        }.items():
            totals[key]["total"] += 1
            if hit:
                totals[key]["correct"] += 1
            else:
                totals[key]["wrong"] += 1

        diagnosis_rows.append(
            {
                "id": clean(row.get("id")),
                "filename": filename,
                "predicted_vlm_model": clean(row.get("predicted_vlm_model")),
                "failure_bucket": failure_bucket,
                "quality_flags": ";".join(flags),
                "expected_color": expected_color,
                "predicted_color": clean(row.get("predicted_color")),
                "expected_color_family": expected_family,
                "predicted_color_family": clean(row.get("predicted_color_family")),
                "expected_color_detail": clean(row.get("expected_color_detail")),
                "predicted_color_detail": clean(row.get("predicted_color_detail")),
                "expected_color_pattern": clean(row.get("expected_color_pattern")),
                "predicted_color_pattern": clean(row.get("predicted_color_pattern")),
                "predicted_opencv_pattern_candidate": clean(row.get("predicted_opencv_pattern_candidate")),
                "predicted_opencv_pattern_reason": clean(row.get("predicted_opencv_pattern_reason")),
                "predicted_vlm_color_signal": clean(row.get("predicted_vlm_color_signal")),
                "predicted_subject_colors_json": clean(row.get("predicted_subject_colors_json")),
                "predicted_frame_colors_json": clean(row.get("predicted_frame_colors_json")),
                "predicted_subject_roi_json": clean(row.get("predicted_subject_roi_json")),
                "expected_water": clean(row.get("expected_water")),
                "predicted_water": clean(row.get("predicted_water")),
                "expected_style": clean(row.get("expected_style")),
                "predicted_style": clean(row.get("predicted_style")),
                "expected_theme": clean(row.get("expected_theme")),
                "predicted_theme": clean(row.get("predicted_theme")),
                "mean_saturation": clean(quality.get("mean_saturation")),
                "saturated_ratio": clean(quality.get("saturated_ratio")),
                "expected_hue_ratio": clean(quality.get("expected_hue_ratio")),
                "overexposed_ratio": clean(quality.get("overexposed_ratio")),
                "gray_ratio": clean(quality.get("gray_ratio")),
            }
        )

    payload = {
        "status": "ok",
        "rows": len(score_rows),
        "score": str(score_path),
        "quality": str(quality_path),
        "metrics": {
            key: {
                "correct": counts["correct"],
                "total": counts["total"],
                "accuracy": round(counts["correct"] / counts["total"], 4) if counts["total"] else None,
                "wrong": counts["wrong"],
            }
            for key, counts in totals.items()
        },
        "failure_buckets": counter_to_dict(Counter(row["failure_bucket"] for row in diagnosis_rows)),
        "quality_flags": counter_to_dict(quality_flags),
        "by_expected_family": nested_counter_to_dict(by_expected_family),
        "by_expected_color": nested_counter_to_dict(by_expected_color),
        "confusions": nested_counter_to_dict(confusions),
        "outputs": {
            "json": str(resolve_path(args.output_json)),
            "csv": str(resolve_path(args.output_csv)),
        },
    }

    write_csv(resolve_path(args.output_csv), diagnosis_rows)
    resolve_path(args.output_json).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def classify_failure(
    *,
    flags: list[str],
    color_hit: bool,
    family_hit: bool,
    detail_hit: bool,
    pattern_hit: bool,
) -> str:
    if color_hit and family_hit and detail_hit and pattern_hit:
        return "all_color_layers_ok"
    if flags and not color_hit:
        return "generation_quality_issue"
    if family_hit and not detail_hit:
        return "fine_color_detail_miss"
    if detail_hit and not pattern_hit:
        return "color_pattern_miss"
    if family_hit and pattern_hit and not color_hit:
        return "canonical_color_merge_issue"
    if not family_hit:
        return "model_color_family_miss"
    return "model_or_postprocess_miss"


def add_confusion(counter: Counter[str], expected: Any, predicted: Any, hit: bool) -> None:
    expected_text = clean(expected)
    if not expected_text or hit:
        return
    predicted_text = clean(predicted) or "(空)"
    counter[f"{expected_text} -> {predicted_text}"] += 1


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def split_flags(value: Any) -> list[str]:
    return [item.strip() for item in clean(value).split(";") if item.strip()]


def filename_key(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    return Path(text).name


def is_hit(value: Any) -> bool:
    return clean(value) == "1"


def counter_to_dict(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def nested_counter_to_dict(data: dict[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {
        key: counter_to_dict(counter)
        for key, counter in sorted(data.items(), key=lambda item: item[0])
    }


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def clean(value: Any) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
