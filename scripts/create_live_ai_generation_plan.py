from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "uploads" / "jade-training-ai"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

VARIANT_INSTRUCTIONS = [
    "change the hand position and camera angle while keeping the same main jade item category",
    "change lighting to a realistic livestream ring-light setup and keep the jade sharply visible",
    "place the item on a live sales tray with the presenter partly visible behind it",
    "use a closer vertical crop with the jade centered and fully visible, no text overlays",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a 4x AI image generation plan from real jade livestream captures."
    )
    parser.add_argument("--real-dir", required=True, type=Path, help="Directory containing the 100 real images.")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--variants-per-image", type=int, default=4)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    real_dir = resolve_path(args.real_dir)
    if not real_dir.exists():
        raise SystemExit(f"real-dir not found: {real_dir}")
    output_dir = resolve_path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_ROOT / real_dir.parent.name
    images = iter_images(real_dir)[: max(1, args.limit)]
    rows: list[dict[str, str]] = []

    for image_index, image in enumerate(images, start=1):
        for variant_index in range(1, max(1, args.variants_per_image) + 1):
            instruction = VARIANT_INSTRUCTIONS[(variant_index - 1) % len(VARIANT_INSTRUCTIONS)]
            target_name = f"ai_{image_index:04d}_{variant_index:02d}.jpg"
            target_image = output_dir / "images" / target_name
            rows.append({
                "id": f"ai-{image_index:04d}-{variant_index:02d}",
                "source_image": relative_to_root(image),
                "target_image": relative_to_root(target_image),
                "variant_index": str(variant_index),
                "generation_prompt": build_prompt(instruction),
                "negative_prompt": negative_prompt(),
                "status": "pending",
            })

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "images").mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "generation_plan.csv"
    jsonl_path = output_dir / "generation_plan.jsonl"
    write_csv(csv_path, rows)
    write_jsonl(jsonl_path, rows)
    print(json.dumps({
        "status": "ok",
        "real_images": len(images),
        "planned_ai_images": len(rows),
        "csv": str(csv_path),
        "jsonl": str(jsonl_path),
        "images_dir": str(output_dir / "images"),
        "next": "Use this JSONL with your image-generation API, then import generated images for /annotate review.",
    }, ensure_ascii=False, indent=2))
    return 0


def build_prompt(variant_instruction: str) -> str:
    return (
        "Use the input image as the visual reference. Generate one photorealistic vertical jade livestream frame. "
        "Preserve the same kind of jade product and realistic jade material cues from the reference, but "
        f"{variant_instruction}. The main jade item must be fully visible, centered enough for YOLO annotation, "
        "sharp, naturally polished, and plausible for a WeChat Channels jade live room. "
        "Do not add readable text, labels, watermarks, QR codes, price tags, duplicated jade objects, or distorted hands."
    )


def negative_prompt() -> str:
    return (
        "text, label, watermark, logo, QR code, price tag, certificate, unreadable UI overlays, duplicate main item, "
        "fake plastic jade, blurry jade, cropped jade, deformed hands, extra fingers, distorted carving"
    )


def iter_images(path: Path) -> list[Path]:
    return sorted(
        [item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda item: str(item.relative_to(path)).lower(),
    )


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = ["id", "source_image", "target_image", "variant_index", "generation_prompt", "negative_prompt", "status"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
