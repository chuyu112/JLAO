from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


OUTPUT_FIELDS = [
    "id",
    "image",
    "expected_color",
    "expected_color_family",
    "expected_color_detail",
    "expected_color_pattern",
    "mean_saturation",
    "p75_saturation",
    "saturated_ratio",
    "expected_hue_ratio",
    "overexposed_ratio",
    "gray_ratio",
    "dark_ratio",
    "hue_bins",
    "flags",
    "error",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check generated jade color-control images for weak color signals.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp" / "jade-color-control-quality.csv")
    parser.add_argument("--mode", choices=["control", "live"], default="control")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--fail-on-weak", action="store_true")
    args = parser.parse_args()

    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except Exception as exc:  # noqa: BLE001
        print(f"OpenCV/numpy unavailable: {exc}", file=sys.stderr)
        return 2

    manifest = resolve_path(args.manifest)
    rows = load_rows(manifest)
    results = [
        inspect_row(row, cv2=cv2, np=np, base_dir=manifest.parent, mode=args.mode)
        for row in rows
    ]

    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    summary = summarize(results, output)
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None))
    return 1 if args.fail_on_weak and summary["weak_images"] else 0


def inspect_row(row: dict[str, Any], *, cv2: Any, np: Any, base_dir: Path, mode: str) -> dict[str, Any]:
    image = clean(row.get("image") or row.get("target_filename") or row.get("filename"))
    expected_family = clean(row.get("expected_color_family") or row.get("color_family"))
    expected_detail = clean(row.get("expected_color_detail") or row.get("color_detail"))
    expected_pattern = clean(row.get("expected_color_pattern") or row.get("color_pattern"))
    result: dict[str, Any] = {
        "id": clean(row.get("id")),
        "image": image,
        "expected_color": clean(row.get("expected_color") or row.get("color")),
        "expected_color_family": expected_family,
        "expected_color_detail": expected_detail,
        "expected_color_pattern": expected_pattern,
        "mean_saturation": "",
        "p75_saturation": "",
        "saturated_ratio": "",
        "expected_hue_ratio": "",
        "overexposed_ratio": "",
        "gray_ratio": "",
        "dark_ratio": "",
        "hue_bins": "{}",
        "flags": "",
        "error": "",
    }
    try:
        path = resolve_image_path(image, base_dir)
        if not path.exists():
            result["error"] = f"image not found: {path}"
            result["flags"] = "missing_image"
            return result

        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if bgr is None:
            result["error"] = f"cannot decode image: {path}"
            result["flags"] = "decode_error"
            return result

        crop = central_crop(bgr)
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        h = hsv[:, :, 0]
        s = hsv[:, :, 1]
        v = hsv[:, :, 2]

        valid = (v >= 25) & (v <= 250)
        if int(valid.sum()) == 0:
            valid = np.ones_like(v, dtype=bool)

        sat_valid = s[valid]
        mean_s = float(np.mean(sat_valid))
        p75_s = float(np.percentile(sat_valid, 75))
        saturated_ratio = float(np.mean((s >= 65) & valid))
        overexposed_ratio = float(np.mean(v >= 245))
        gray_ratio = float(np.mean((s <= 35) & (v >= 45) & (v <= 245)))
        dark_ratio = float(np.mean(v <= 65))
        expected_hue_ratio = hue_ratio(h, s, v, expected_family, expected_detail, expected_pattern)
        bins = hue_bins(h, s, v)

        flags = quality_flags(
            mode=mode,
            expected_family=expected_family,
            expected_detail=expected_detail,
            expected_pattern=expected_pattern,
            mean_s=mean_s,
            p75_s=p75_s,
            saturated_ratio=saturated_ratio,
            expected_hue_ratio=expected_hue_ratio,
            overexposed_ratio=overexposed_ratio,
            gray_ratio=gray_ratio,
            dark_ratio=dark_ratio,
        )

        result.update(
            {
                "mean_saturation": round(mean_s, 2),
                "p75_saturation": round(p75_s, 2),
                "saturated_ratio": round(saturated_ratio, 4),
                "expected_hue_ratio": round(expected_hue_ratio, 4),
                "overexposed_ratio": round(overexposed_ratio, 4),
                "gray_ratio": round(gray_ratio, 4),
                "dark_ratio": round(dark_ratio, 4),
                "hue_bins": json.dumps(bins, ensure_ascii=False, sort_keys=True),
                "flags": ";".join(flags),
            }
        )
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
        result["flags"] = "quality_check_error"
    return result


def quality_flags(
    *,
    mode: str,
    expected_family: str,
    expected_detail: str,
    expected_pattern: str,
    mean_s: float,
    p75_s: float,
    saturated_ratio: float,
    expected_hue_ratio: float,
    overexposed_ratio: float,
    gray_ratio: float,
    dark_ratio: float,
) -> list[str]:
    flags: list[str] = []
    is_white = expected_family == "白色无色" or expected_detail in {"白冰", "无色"}
    is_black = expected_family == "黑色" or expected_detail == "墨翠"
    is_multicolor = expected_family == "多彩" or expected_pattern in {"春带彩", "多彩"}
    is_gold_pattern = expected_pattern == "洒金"

    if overexposed_ratio >= 0.38 and not is_white:
        flags.append("overexposed")
    if is_white:
        if overexposed_ratio >= 0.55:
            flags.append("white_overexposed")
        if dark_ratio >= 0.35:
            flags.append("too_dark_for_white")
        return flags
    if is_black:
        if dark_ratio < 0.25:
            flags.append("not_dark_enough_for_mowcui")
        if mean_s < 35:
            flags.append("weak_green_signal_for_mowcui")
        return flags

    if mode == "live":
        if overexposed_ratio >= 0.5:
            flags.append("severe_overexposed")
        if mean_s < 38 or p75_s < 55:
            flags.append("weak_saturation")
        if saturated_ratio < 0.05:
            flags.append("very_low_saturated_coverage")
        if gray_ratio >= 0.68:
            flags.append("too_gray")
        if expected_hue_ratio < 0.03 and not is_multicolor and not is_gold_pattern:
            flags.append("very_low_expected_hue")
        if expected_hue_ratio < 0.05 and is_multicolor:
            flags.append("very_low_multicolor_hue")
        if expected_hue_ratio < 0.02 and is_gold_pattern:
            flags.append("very_low_gold_signal")
        return flags

    if mean_s < 55 or p75_s < 75:
        flags.append("weak_saturation")
    if saturated_ratio < 0.18:
        flags.append("low_saturated_coverage")
    if gray_ratio >= 0.52:
        flags.append("too_gray")
    if expected_hue_ratio < 0.1 and not is_multicolor and not is_gold_pattern:
        flags.append("low_expected_hue")
    if expected_hue_ratio < 0.16 and is_multicolor:
        flags.append("low_multicolor_hue")
    if expected_hue_ratio < 0.06 and is_gold_pattern:
        flags.append("low_gold_signal")
    return flags


def hue_ratio(h: Any, s: Any, v: Any, family: str, detail: str, pattern: str) -> float:
    color_mask = (s >= 55) & (v >= 35) & (v <= 245)
    if detail == "墨翠" or family == "黑色":
        return float(((v <= 85) & (s >= 25)).mean())
    if pattern == "洒金":
        return float((color_mask & (h >= 15) & (h <= 42)).mean())
    if pattern == "春带彩":
        green = color_mask & (h >= 35) & (h <= 95)
        purple = color_mask & (h >= 118) & (h <= 165)
        return float(green.mean() + purple.mean())
    if family == "多彩" or pattern == "多彩":
        return multicolor_ratio(h, s, v)
    if family == "绿色":
        return float((color_mask & (h >= 35) & (h <= 95)).mean())
    if family == "蓝绿色":
        return float((color_mask & (h >= 65) & (h <= 112)).mean())
    if family == "紫色":
        return float((color_mask & (h >= 118) & (h <= 165)).mean())
    if family == "黄色":
        return float((color_mask & (h >= 15) & (h <= 45)).mean())
    if family == "红色":
        return float((color_mask & ((h <= 10) | (h >= 168))).mean())
    return float(color_mask.mean())


def multicolor_ratio(h: Any, s: Any, v: Any) -> float:
    color_mask = (s >= 55) & (v >= 35) & (v <= 245)
    green = color_mask & (h >= 35) & (h <= 95)
    purple = color_mask & (h >= 118) & (h <= 165)
    yellow = color_mask & (h >= 15) & (h <= 45)
    red = color_mask & ((h <= 10) | (h >= 168))
    blue = color_mask & (h >= 96) & (h <= 125)
    return float(green.mean() + purple.mean() + yellow.mean() + red.mean() + blue.mean())


def hue_bins(h: Any, s: Any, v: Any) -> dict[str, float]:
    color_mask = (s >= 55) & (v >= 35) & (v <= 245)
    bins = {
        "red": color_mask & ((h <= 10) | (h >= 168)),
        "yellow": color_mask & (h >= 15) & (h <= 45),
        "green": color_mask & (h >= 35) & (h <= 95),
        "blue_green": color_mask & (h >= 65) & (h <= 112),
        "blue": color_mask & (h >= 96) & (h <= 125),
        "purple": color_mask & (h >= 118) & (h <= 165),
    }
    return {key: round(float(mask.mean()), 4) for key, mask in bins.items()}


def central_crop(image: Any) -> Any:
    height, width = image.shape[:2]
    y0 = int(height * 0.1)
    y1 = int(height * 0.9)
    x0 = int(width * 0.1)
    x1 = int(width * 0.9)
    if y1 <= y0 or x1 <= x0:
        return image
    return image[y0:y1, x0:x1]


def summarize(rows: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    weak = [row for row in rows if clean(row.get("flags"))]
    errors = [row for row in rows if clean(row.get("error"))]
    return {
        "status": "ok",
        "rows": len(rows),
        "weak_images": len(weak),
        "errors": len(errors),
        "output": str(output),
        "top_flags": flag_counts(weak),
    }


def flag_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for flag in clean(row.get("flags")).split(";"):
            if flag:
                counts[flag] = counts.get(flag, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def resolve_image_path(raw: str, base_dir: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    root_path = (ROOT / path).resolve()
    if root_path.exists():
        return root_path
    return (base_dir / path).resolve()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def clean(value: Any) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    raise SystemExit(main())
