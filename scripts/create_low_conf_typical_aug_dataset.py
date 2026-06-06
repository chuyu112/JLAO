from __future__ import annotations

import argparse
import csv
import json
import math
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "tmp" / "low_conf_jade_backend" / "summary.json"
DEFAULT_OUTPUT = ROOT / "data" / "jade_low_conf_typical_aug_100"


EXCLUDED_SAMPLE_NUMBERS = {6, 11}
MANUAL_BOXES_BY_NAME = {
    "phone-e3f8af7281b7.jpg": [242.0, 224.0, 461.0, 710.0],
    "phone-f59dd648fa03.jpg": [72.0, 142.0, 370.0, 620.0],
    "phone-4a3318802e34.jpg": [86.0, 40.0, 405.0, 828.0],
}
MERGED_BOXES_BY_NAME = {
    "phone-28d0bb2d6c1a.jpg": [37.2, 374.48, 461.0, 791.98],
}


@dataclass(frozen=True)
class SourceSample:
    sample_number: int
    source_image: Path
    box: list[float]
    kind: str
    source_confidence: float


def sample_number_from_overlay(path: str) -> int | None:
    name = Path(path).name
    prefix = name.split("_", 1)[0]
    try:
        return int(prefix)
    except ValueError:
        return None


def load_sources(summary_path: Path) -> list[SourceSample]:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    sources: list[SourceSample] = []
    selected = payload.get("selected") if isinstance(payload.get("selected"), list) else []
    for item in selected:
        if not isinstance(item, dict):
            continue
        sample_number = sample_number_from_overlay(str(item.get("overlay") or ""))
        if sample_number is None or sample_number in EXCLUDED_SAMPLE_NUMBERS:
            continue
        local_image = Path(str(item.get("local_image") or ""))
        if not local_image.exists():
            continue
        image_name = local_image.name
        raw_box = item.get("box")
        if image_name in MANUAL_BOXES_BY_NAME:
            box = MANUAL_BOXES_BY_NAME[image_name]
            kind = "manual-no-detection"
        elif image_name in MERGED_BOXES_BY_NAME:
            box = MERGED_BOXES_BY_NAME[image_name]
            kind = "merged-low-conf"
        elif isinstance(raw_box, list) and len(raw_box) == 4:
            box = [float(value) for value in raw_box]
            kind = "low-conf"
        else:
            continue
        sources.append(
            SourceSample(
                sample_number=sample_number,
                source_image=local_image,
                box=[float(value) for value in box],
                kind=kind,
                source_confidence=float(item.get("confidence") or 0.0),
            )
        )
    sources.sort(key=lambda item: item.sample_number)
    return sources


def reset_output(output_dir: Path) -> None:
    for relative in [
        "images/train",
        "images/val",
        "labels/train",
        "labels/val",
        "qa/overlays/train",
        "qa/overlays/val",
        "qa/source_boxes",
    ]:
        path = output_dir / relative
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def affine_matrices(width: int, height: int, rng: random.Random) -> tuple[tuple[float, ...], tuple[float, ...], dict[str, float]]:
    angle = rng.uniform(-5.5, 5.5)
    scale_x = rng.uniform(0.94, 1.07)
    scale_y = rng.uniform(0.94, 1.07)
    shear = math.radians(rng.uniform(-4.0, 4.0))
    tx = rng.uniform(-20.0, 20.0)
    ty = rng.uniform(-28.0, 28.0)
    theta = math.radians(angle)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    cx = width / 2.0
    cy = height / 2.0

    # Forward matrix source -> output. Non-uniform scale and shear preserve the
    # rotated/elliptical side-view problem instead of forcing circular geometry.
    a0 = scale_x
    b0 = math.tan(shear) * scale_y
    d0 = 0.0
    e0 = scale_y
    a = cos_t * a0 - sin_t * d0
    b = cos_t * b0 - sin_t * e0
    d = sin_t * a0 + cos_t * d0
    e = sin_t * b0 + cos_t * e0
    c = cx + tx - a * cx - b * cy
    f = cy + ty - d * cx - e * cy

    det = a * e - b * d
    ia = e / det
    ib = -b / det
    id_ = -d / det
    ie = a / det
    ic = -(ia * c + ib * f)
    iff = -(id_ * c + ie * f)
    return (a, b, c, d, e, f), (ia, ib, ic, id_, ie, iff), {
        "angle": angle,
        "scale_x": scale_x,
        "scale_y": scale_y,
        "shear": math.degrees(shear),
        "tx": tx,
        "ty": ty,
    }


def transform_box(box: list[float], matrix: tuple[float, ...], width: int, height: int) -> list[float]:
    a, b, c, d, e, f = matrix
    x1, y1, x2, y2 = box
    points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    transformed = [(a * x + b * y + c, d * x + e * y + f) for x, y in points]
    xs = [point[0] for point in transformed]
    ys = [point[1] for point in transformed]
    return [
        max(0.0, min(float(width - 1), min(xs))),
        max(0.0, min(float(height - 1), min(ys))),
        max(0.0, min(float(width - 1), max(xs))),
        max(0.0, min(float(height - 1), max(ys))),
    ]


def to_yolo(box: list[float], width: int, height: int) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    return (
        ((x1 + x2) / 2.0) / width,
        ((y1 + y2) / 2.0) / height,
        (x2 - x1) / width,
        (y2 - y1) / height,
    )


def validate_box(box: list[float], width: int, height: int) -> None:
    x1, y1, x2, y2 = box
    if x2 <= x1 + 8 or y2 <= y1 + 8:
        raise ValueError(f"box too small: {box}")
    values = to_yolo(box, width, height)
    if not all(0.0 < value <= 1.0 for value in values):
        raise ValueError(f"invalid yolo box: {values}")


def augment_image(image: Image.Image, box: list[float], rng: random.Random) -> Image.Image:
    result = image.convert("RGB")
    result = ImageEnhance.Brightness(result).enhance(rng.uniform(0.82, 1.18))
    result = ImageEnhance.Contrast(result).enhance(rng.uniform(0.86, 1.18))
    result = ImageEnhance.Color(result).enhance(rng.uniform(0.84, 1.22))
    result = ImageEnhance.Sharpness(result).enhance(rng.uniform(0.70, 1.35))
    if rng.random() < 0.45:
        result = result.filter(ImageFilter.GaussianBlur(rng.uniform(0.18, 1.05)))
    if rng.random() < 0.28:
        channels = list(result.split())
        channel = rng.choice([0, 2])
        channels[channel] = ImageChops.offset(channels[channel], rng.choice([-7, -4, 4, 7]), 0)
        result = Image.merge("RGB", channels)
    if rng.random() < 0.35:
        overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay, "RGBA")
        x1, y1, x2, y2 = box
        for _ in range(rng.randint(1, 3)):
            draw.line(
                [
                    (rng.uniform(x1, x2), rng.uniform(y1, y2)),
                    (rng.uniform(x1, x2), rng.uniform(y1, y2)),
                ],
                fill=(255, 255, 255, rng.randint(24, 68)),
                width=rng.randint(2, 5),
            )
        result = Image.alpha_composite(result.convert("RGBA"), overlay).convert("RGB")
    return result


def draw_box(image: Image.Image, box: list[float], label: str) -> Image.Image:
    preview = image.convert("RGB")
    draw = ImageDraw.Draw(preview, "RGBA")
    x1, y1, x2, y2 = box
    draw.rectangle([x1, y1, x2, y2], outline=(255, 91, 0, 255), width=5)
    draw.rectangle([x1, max(0, y1 - 30), min(preview.width, x1 + 190), y1], fill=(255, 91, 0, 220))
    draw.text((x1 + 7, max(0, y1 - 23)), label, fill=(255, 255, 255, 255))
    return preview


def make_contact_sheet(paths: list[Path], output_path: Path) -> None:
    thumbs: list[Image.Image] = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        image.thumbnail((160, 290), Image.Resampling.LANCZOS)
        tile = Image.new("RGB", (160, 290), (20, 22, 26))
        tile.paste(image, ((160 - image.width) // 2, (290 - image.height) // 2))
        thumbs.append(tile)
    cols = 5
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 160, rows * 290), (245, 245, 245))
    for index, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((index % cols) * 160, (index // cols) * 290))
    sheet.save(output_path, quality=90)


def write_dataset_yaml(output_dir: Path) -> None:
    text = "\n".join(
        [
            f"path: {output_dir.resolve().as_posix()}",
            "train: images/train",
            "val: images/val",
            "names:",
            "  0: jade_bangle",
            "",
        ]
    )
    (output_dir / "dataset.yaml").write_text(text, encoding="utf-8")


def parse_sample_numbers(raw: str) -> set[int]:
    values: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        values.add(int(item))
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Create YOLO samples from low-confidence typical jade livestream frames.")
    parser.add_argument("--summary", type=Path, default=SUMMARY_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--variants-per-source", type=int, default=10)
    parser.add_argument(
        "--hard-sample-numbers",
        default="",
        help="comma-separated source sample numbers that need extra variants, e.g. 4,9,12",
    )
    parser.add_argument("--hard-extra-variants", type=int, default=0)
    parser.add_argument("--seed", type=int, default=606236)
    args = parser.parse_args()

    sources = load_sources(args.summary)
    if not sources:
        raise SystemExit("no usable source samples")

    reset_output(args.output_dir)
    write_dataset_yaml(args.output_dir)
    rng = random.Random(args.seed)
    hard_sample_numbers = parse_sample_numbers(args.hard_sample_numbers)
    rows: list[dict[str, Any]] = []
    overlay_paths: list[Path] = []

    for source in sources:
        image = Image.open(source.source_image).convert("RGB")
        width, height = image.size
        box = source.box
        validate_box(box, width, height)
        source_preview = draw_box(image, box, f"source {source.sample_number:02d}")
        source_preview.save(args.output_dir / "qa" / "source_boxes" / f"source_{source.sample_number:02d}.jpg", quality=92)

        total_variants = args.variants_per_source
        if source.sample_number in hard_sample_numbers:
            total_variants += args.hard_extra_variants

        for variant in range(1, total_variants + 1):
            forward, inverse, transform_meta = affine_matrices(width, height, rng)
            transformed = image.transform(
                (width, height),
                Image.Transform.AFFINE,
                inverse,
                resample=Image.Resampling.BICUBIC,
                fillcolor=(18, 20, 23),
            )
            out_box = transform_box(box, forward, width, height)
            validate_box(out_box, width, height)
            augmented = augment_image(transformed, out_box, rng)
            split = "val" if variant == total_variants else "train"
            stem = f"low_conf_typical_{source.sample_number:02d}_{variant:02d}"
            image_path = args.output_dir / "images" / split / f"{stem}.jpg"
            label_path = args.output_dir / "labels" / split / f"{stem}.txt"
            overlay_path = args.output_dir / "qa" / "overlays" / split / f"{stem}.jpg"
            augmented.save(image_path, quality=rng.randint(74, 94), optimize=True)
            cx, cy, bw, bh = to_yolo(out_box, width, height)
            label_path.write_text(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n", encoding="utf-8")
            draw_box(augmented, out_box, f"jade {source.sample_number:02d}").save(overlay_path, quality=90)
            if len(overlay_paths) < 50:
                overlay_paths.append(overlay_path)
            rows.append(
                {
                    "split": split,
                    "image": str(image_path.relative_to(args.output_dir)).replace("\\", "/"),
                    "label": str(label_path.relative_to(args.output_dir)).replace("\\", "/"),
                    "source_sample": source.sample_number,
                    "source_image": str(source.source_image),
                    "source_kind": source.kind,
                    "source_confidence": source.source_confidence,
                    "bbox_xyxy": ",".join(f"{value:.2f}" for value in out_box),
                    "bbox_yolo": f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}",
                    **{key: round(value, 4) for key, value in transform_meta.items()},
                }
            )

    with (args.output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    make_contact_sheet(overlay_paths, args.output_dir / "preview_first_50.jpg")

    summary = {
        "output_dir": str(args.output_dir.resolve()),
        "sources": len(sources),
        "variants_per_source": args.variants_per_source,
        "hard_sample_numbers": sorted(hard_sample_numbers),
        "hard_extra_variants": args.hard_extra_variants,
        "total_images": len(rows),
        "train_images": sum(1 for row in rows if row["split"] == "train"),
        "val_images": sum(1 for row in rows if row["split"] == "val"),
        "dataset_yaml": str((args.output_dir / "dataset.yaml").resolve()),
        "preview": str((args.output_dir / "preview_first_50.jpg").resolve()),
        "excluded_sample_numbers": sorted(EXCLUDED_SAMPLE_NUMBERS),
        "source_numbers": [source.sample_number for source in sources],
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
