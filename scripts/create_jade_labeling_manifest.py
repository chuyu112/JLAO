from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
FIELDNAMES = [
    "image_path",
    "text",
    "color",
    "water",
    "style",
    "theme",
    "notes",
    "batch_id",
]


def discover_images(image_dir: Path, *, recursive: bool = False) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    return sorted(
        path
        for path in image_dir.glob(pattern)
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def display_path(path: Path, *, relative_to: Path | None = None) -> str:
    if relative_to is None:
        return str(path)
    try:
        return str(path.relative_to(relative_to))
    except ValueError:
        return str(path)


def manifest_rows(images: list[Path], *, relative_to: Path | None = None, batch_id: str = "") -> list[dict[str, str]]:
    return [
        {
            "image_path": display_path(path, relative_to=relative_to),
            "text": "",
            "color": "",
            "water": "",
            "style": "",
            "theme": "",
            "notes": "",
            "batch_id": batch_id,
        }
        for path in images
    ]


def write_manifest(output: Path, rows: list[dict[str, str]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a jade image labeling manifest CSV template.")
    parser.add_argument("--image-dir", required=True, type=Path, help="Directory containing jade images.")
    parser.add_argument("--output", required=True, type=Path, help="Output CSV manifest path.")
    parser.add_argument("--recursive", action="store_true", help="Scan image directory recursively.")
    parser.add_argument("--relative-to", type=Path, help="Make image paths relative to this directory.")
    parser.add_argument("--batch-id", default="", help="Optional batch id written to every row.")
    args = parser.parse_args()

    images = discover_images(args.image_dir, recursive=args.recursive)
    rows = manifest_rows(images, relative_to=args.relative_to, batch_id=args.batch_id)
    write_manifest(args.output, rows)
    print(f"wrote {len(rows)} jade labeling rows to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
