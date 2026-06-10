from __future__ import annotations

import argparse
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEEDBACK_PATH = ROOT / "data" / "jade_feedback.jsonl"
DEFAULT_UPLOAD_ROOT = ROOT / "uploads" / "jade-annotation-images"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Register local jade images as pending manual annotation tasks.")
    parser.add_argument("--image-dir", required=True, type=Path)
    parser.add_argument("--feedback-path", type=Path, default=DEFAULT_FEEDBACK_PATH)
    parser.add_argument("--batch-id", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--source", default="manual-image-import")
    parser.add_argument("--no-copy", action="store_true", help="Use original paths; only works well when images are under uploads/.")
    args = parser.parse_args()

    image_dir = resolve_path(args.image_dir)
    if not image_dir.exists():
        raise SystemExit(f"image-dir not found: {image_dir}")

    batch_id = args.batch_id.strip() or datetime.now().strftime("annotation-import-%Y%m%d-%H%M%S")
    images = iter_images(image_dir)
    if args.limit and args.limit > 0:
        images = images[: args.limit]

    records: list[dict[str, Any]] = []
    for index, source_image in enumerate(images, start=1):
        target = source_image
        if not args.no_copy:
            target_dir = DEFAULT_UPLOAD_ROOT / batch_id
            target_dir.mkdir(parents=True, exist_ok=True)
            target = unique_path(target_dir / f"{index:04d}{source_image.suffix.lower() or '.jpg'}")
            shutil.copy2(source_image, target)
        records.append(build_record(target, batch_id=batch_id, source=args.source, source_image=source_image))

    feedback_path = resolve_path(args.feedback_path)
    feedback_path.parent.mkdir(parents=True, exist_ok=True)
    with feedback_path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    print(json.dumps({
        "status": "ok",
        "batch_id": batch_id,
        "image_dir": str(image_dir),
        "registered": len(records),
        "feedback_path": str(feedback_path),
        "next": "Open http://127.0.0.1:5173/annotate and draw boxes.",
    }, ensure_ascii=False, indent=2))
    return 0


def build_record(image_path: Path, *, batch_id: str, source: str, source_image: Path) -> dict[str, Any]:
    image_ref = public_upload_ref(image_path)
    return {
        "id": f"jade-annotation-{uuid.uuid4().hex[:12]}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "image": image_ref,
            "batch_id": batch_id,
            "source_filename": source_image.name,
            "import_source": str(source_image),
        },
        "predicted": {},
        "corrected": {"color": "", "water": "", "style": "", "theme": ""},
        "evidence": {"images": [image_ref], "texts": [], "detections": []},
        "confidence": 0.0,
        "source": source,
        "attribute_sources": {},
        "needs_review": True,
        "review_status": "pending",
        "review_reason": "needs-human-yolo-box",
        "training": {
            "suggested_classes": [],
            "yolo_ready": False,
            "requires_manual_box": True,
            "box_mode": "",
        },
    }


def iter_images(path: Path) -> list[Path]:
    return sorted(
        [item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda item: str(item.relative_to(path)).lower(),
    )


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    index = 1
    while True:
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def public_upload_ref(path: Path) -> str:
    try:
        relative = path.resolve().relative_to((ROOT / "uploads").resolve())
        return "/uploads/" + str(relative).replace("\\", "/")
    except ValueError:
        return str(path)


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
