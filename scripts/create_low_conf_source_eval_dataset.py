from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from create_low_conf_typical_aug_dataset import load_sources, to_yolo, validate_box


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUMMARY = ROOT / "tmp" / "low_conf_jade_backend" / "summary.json"
DEFAULT_OUTPUT = ROOT / "data" / "jade_low_conf_typical_source_eval_10"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a YOLO eval set from the original low-confidence typical source frames.")
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    sources = load_sources(args.summary)
    if not sources:
        raise SystemExit("no source samples found")

    if args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    for relative in ["images/test", "labels/test"]:
        (args.output_dir / relative).mkdir(parents=True, exist_ok=True)

    rows = []
    for source in sources:
        try:
            from PIL import Image
        except ImportError as exc:
            raise SystemExit("Pillow is required") from exc
        with Image.open(source.source_image) as image:
            width, height = image.size
        validate_box(source.box, width, height)
        stem = f"source_{source.sample_number:02d}_{source.source_image.stem}"
        image_out = args.output_dir / "images" / "test" / f"{stem}{source.source_image.suffix.lower()}"
        label_out = args.output_dir / "labels" / "test" / f"{stem}.txt"
        shutil.copy2(source.source_image, image_out)
        cx, cy, bw, bh = to_yolo(source.box, width, height)
        label_out.write_text(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n", encoding="utf-8")
        rows.append(
            {
                "source_sample": source.sample_number,
                "source_image": str(source.source_image),
                "image": str(image_out.relative_to(args.output_dir)).replace("\\", "/"),
                "label": str(label_out.relative_to(args.output_dir)).replace("\\", "/"),
                "box": source.box,
                "source_kind": source.kind,
                "source_confidence": source.source_confidence,
            }
        )

    dataset_yaml = "\n".join(
        [
            f"path: {args.output_dir.resolve().as_posix()}",
            "train: images/test",
            "val: images/test",
            "test: images/test",
            "names:",
            "  0: jade_bangle",
            "",
        ]
    )
    (args.output_dir / "dataset.yaml").write_text(dataset_yaml, encoding="utf-8")
    summary = {
        "output_dir": str(args.output_dir.resolve()),
        "images": len(rows),
        "source_numbers": [row["source_sample"] for row in rows],
        "dataset_yaml": str((args.output_dir / "dataset.yaml").resolve()),
        "rows": rows,
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
