from __future__ import annotations

import argparse
import csv
import json
import shutil
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "jade_bangle_combined_training_430"
DEFAULT_LOW_CONF_ROOT = ROOT / "data" / "jade_low_conf_typical_aug_100"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class DatasetSpec:
    slug: str
    root: Path
    splits: tuple[str, ...]
    split_overrides: dict[str, str] | None = None

    def output_split(self, input_split: str) -> str:
        if self.split_overrides and input_split in self.split_overrides:
            return self.split_overrides[input_split]
        return input_split


def dataset_specs(low_conf_root: Path, low_conf_slug: str) -> tuple[DatasetSpec, ...]:
    return (
        DatasetSpec(
            slug="composite_v2",
            root=ROOT / "data" / "jade_bangle_composite_200_v2",
            splits=("train", "val", "test"),
        ),
        DatasetSpec(
            slug="liveroom_100",
            root=ROOT / "data" / "generated_jade_bangle_liveroom_100",
            splits=("train", "val"),
        ),
        DatasetSpec(
            slug=low_conf_slug,
            root=low_conf_root,
            splits=("train", "val"),
        ),
        DatasetSpec(
            slug="real_bmp_20",
            root=ROOT / "data" / "real_bangle_bmp_ai20",
            splits=("train",),
        ),
        DatasetSpec(
            slug="low_conf_source_10",
            root=ROOT / "data" / "jade_low_conf_typical_source_eval_10",
            splits=("test",),
            split_overrides={"test": "train"},
        ),
    )


def reset_output(output_dir: Path) -> None:
    for relative in [
        "images/train",
        "images/val",
        "images/test",
        "labels/train",
        "labels/val",
        "labels/test",
    ]:
        path = output_dir / relative
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def image_files(path: Path) -> list[Path]:
    return sorted(item for item in path.iterdir() if item.is_file() and item.suffix.lower() in IMAGE_SUFFIXES)


def validate_label(label_path: Path) -> list[str]:
    issues: list[str] = []
    text = label_path.read_text(encoding="utf-8").strip()
    if not text:
        return [f"empty label: {label_path}"]
    for line_number, line in enumerate(text.splitlines(), start=1):
        parts = line.split()
        if len(parts) != 5:
            issues.append(f"{label_path}:{line_number}: expected 5 YOLO fields")
            continue
        if parts[0] != "0":
            issues.append(f"{label_path}:{line_number}: expected class 0, got {parts[0]}")
        try:
            values = [float(value) for value in parts[1:]]
        except ValueError:
            issues.append(f"{label_path}:{line_number}: non-numeric coordinates")
            continue
        if not all(0.0 < value <= 1.0 for value in values):
            issues.append(f"{label_path}:{line_number}: coordinates out of range {values}")
    return issues


def copy_dataset(spec: DatasetSpec, output_dir: Path) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    issues: list[str] = []
    for input_split in spec.splits:
        out_split = spec.output_split(input_split)
        image_dir = spec.root / "images" / input_split
        label_dir = spec.root / "labels" / input_split
        if not image_dir.exists() or not label_dir.exists():
            issues.append(f"missing split directories: {spec.slug}:{input_split}")
            continue
        for image_path in image_files(image_dir):
            label_path = label_dir / f"{image_path.stem}.txt"
            if not label_path.exists():
                issues.append(f"missing label for {image_path}")
                continue
            label_issues = validate_label(label_path)
            if label_issues:
                issues.extend(label_issues)
                continue
            out_stem = f"{spec.slug}__{input_split}__{image_path.stem}"
            out_image = output_dir / "images" / out_split / f"{out_stem}{image_path.suffix.lower()}"
            out_label = output_dir / "labels" / out_split / f"{out_stem}.txt"
            shutil.copy2(image_path, out_image)
            # Re-write the class id to 0 defensively, while preserving boxes.
            rewritten_lines = []
            for line in label_path.read_text(encoding="utf-8").strip().splitlines():
                parts = line.split()
                rewritten_lines.append(" ".join(["0", *parts[1:5]]))
            out_label.write_text("\n".join(rewritten_lines) + "\n", encoding="utf-8")
            rows.append(
                {
                    "source_dataset": spec.slug,
                    "source_split": input_split,
                    "split": out_split,
                    "source_image": str(image_path.relative_to(ROOT)).replace("\\", "/"),
                    "image": str(out_image.relative_to(output_dir)).replace("\\", "/"),
                    "label": str(out_label.relative_to(output_dir)).replace("\\", "/"),
                }
            )
    return rows, issues


def write_dataset_yaml(output_dir: Path) -> None:
    text = "\n".join(
        [
            f"path: {output_dir.resolve().as_posix()}",
            "train: images/train",
            "val: images/val",
            "test: images/test",
            "names:",
            "  0: jade_bangle",
            "",
        ]
    )
    (output_dir / "dataset.yaml").write_text(text, encoding="utf-8")


def split_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = {"train": 0, "val": 0, "test": 0}
    for row in rows:
        counts[row["split"]] = counts.get(row["split"], 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Combine curated jade bangle YOLO datasets into one training dataset.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--low-conf-root", type=Path, default=DEFAULT_LOW_CONF_ROOT)
    parser.add_argument("--low-conf-slug", default="low_conf")
    args = parser.parse_args()

    low_conf_root = args.low_conf_root if args.low_conf_root.is_absolute() else (ROOT / args.low_conf_root).resolve()
    specs = dataset_specs(low_conf_root, args.low_conf_slug)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reset_output(args.output_dir)
    all_rows: list[dict[str, str]] = []
    all_issues: list[str] = []
    for spec in specs:
        rows, issues = copy_dataset(spec, args.output_dir)
        all_rows.extend(rows)
        all_issues.extend(issues)
    if all_issues:
        issue_text = "\n".join(all_issues[:80])
        raise SystemExit(f"dataset combine failed with {len(all_issues)} issue(s):\n{issue_text}")

    write_dataset_yaml(args.output_dir)
    manifest_path = args.output_dir / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)

    summary = {
        "output_dir": str(args.output_dir.resolve()),
        "total_images": len(all_rows),
        "split_counts": split_counts(all_rows),
        "datasets": [
            {
                "slug": spec.slug,
                "root": str(spec.root.relative_to(ROOT)),
                "splits": list(spec.splits),
            }
            for spec in specs
        ],
        "dataset_yaml": str((args.output_dir / "dataset.yaml").resolve()),
        "manifest": str(manifest_path.resolve()),
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
