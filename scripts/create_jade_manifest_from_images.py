from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_multimodal_service import JADE_COLORS, JADE_STYLES, JADE_THEMES, JADE_WATERS  # noqa: E402
from app.services.jade_training_service import IMAGE_EXTENSIONS, class_names_from_feedback  # noqa: E402


FIELDS = ["image", "color", "water", "style", "theme", "text", "class_name", "x_center", "y_center", "width", "height"]
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
    parser = argparse.ArgumentParser(description="Create a jade training manifest CSV by scanning an image directory.")
    parser.add_argument("--image-dir", required=True, type=Path, help="Directory containing jade images.")
    parser.add_argument("--output", required=True, type=Path, help="CSV manifest output path.")
    parser.add_argument("--recursive", action="store_true", help="Scan image directory recursively.")
    parser.add_argument("--relative", action="store_true", help="Write image paths relative to the output manifest directory.")
    parser.add_argument("--whole-image-box", action="store_true", help="Fill 0.5,0.50,0.85,0.85 for single-class rows.")
    args = parser.parse_args()

    image_dir = resolve_path(args.image_dir)
    output_path = resolve_path(args.output)
    if not image_dir.exists() or not image_dir.is_dir():
        print(f"image dir not found: {image_dir}", file=sys.stderr)
        return 2

    images = list(iter_images(image_dir, recursive=args.recursive))
    rows = [row_for_image(path, output_path.parent, relative=args.relative, whole_image_box=args.whole_image_box) for path in images]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {len(rows)} rows to {output_path}")
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def iter_images(image_dir: Path, *, recursive: bool) -> list[Path]:
    pattern = "**/*" if recursive else "*"
    return sorted(
        [path for path in image_dir.glob(pattern) if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda path: str(path).lower(),
    )


def row_for_image(image_path: Path, manifest_dir: Path, *, relative: bool, whole_image_box: bool) -> dict[str, Any]:
    path_text = " ".join([image_path.stem, *[part for part in image_path.parent.parts]])
    attrs = {key: first_attribute(key, path_text) for key in ATTRIBUTE_KEYS}
    classes = class_names_from_feedback({"corrected": {"style": attrs["style"], "theme": attrs["theme"]}})
    single_class = len(classes) == 1
    image_value = str(image_path)
    if relative:
        try:
            image_value = str(image_path.relative_to(manifest_dir))
        except ValueError:
            image_value = str(image_path)
    return {
        "image": image_value,
        "color": attrs["color"],
        "water": attrs["water"],
        "style": attrs["style"],
        "theme": attrs["theme"],
        "text": "",
        "class_name": ",".join(classes),
        "x_center": "0.5" if whole_image_box and single_class else "",
        "y_center": "0.5" if whole_image_box and single_class else "",
        "width": "0.85" if whole_image_box and single_class else "",
        "height": "0.85" if whole_image_box and single_class else "",
    }


def first_attribute(key: str, text: str) -> str:
    catalog = ATTRIBUTE_CATALOGS[key]
    normalized = text.replace("_", " ").replace("-", " ")
    for canonical, aliases in catalog.items():
        if canonical in normalized:
            return canonical
        if any(alias and alias in normalized for alias in aliases):
            return canonical
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
