from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ARTIFACTS = [
    "models/jade-yolo.pt",
    "models/jade-yolo-card.md",
    "data/jade_yolo/dataset.yaml",
    "data/jade_yolo_class_reference.csv",
    "data/jade_eval_baseline.json",
    "data/jade_eval_after_train.json",
    "data/jade_eval_comparison.json",
    "data/jade_eval_summary.md",
    "docs/jade_multimodal_training.md",
]
OPTIONAL_ARTIFACTS = [
    "data/jade_eval_mistakes.csv",
]


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a packaged jade model artifact zip for required files.")
    parser.add_argument("--package", type=Path, default=ROOT / "models" / "jade-yolo-artifacts.zip")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    package_path = resolve_path(args.package)
    if not package_path.exists():
        print(json.dumps({"status": "missing-package", "package": str(package_path)}, ensure_ascii=False))
        return 2

    try:
        names = package_names(package_path)
    except zipfile.BadZipFile:
        print(json.dumps({"status": "invalid-zip", "package": str(package_path)}, ensure_ascii=False))
        return 2

    normalized = {normalize_name(name) for name in names}
    missing_required = [item for item in REQUIRED_ARTIFACTS if item not in normalized]
    present_optional = [item for item in OPTIONAL_ARTIFACTS if item in normalized]
    payload = {
        "status": "ok" if not missing_required else "missing-required",
        "package": str(package_path),
        "entries": len(names),
        "required": {
            "expected": REQUIRED_ARTIFACTS,
            "missing": missing_required,
        },
        "optional": {
            "expected": OPTIONAL_ARTIFACTS,
            "present": present_optional,
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if not missing_required else 3


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def package_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path, "r") as handle:
        return handle.namelist()


def normalize_name(name: str) -> str:
    return name.replace("\\", "/").lstrip("./")


if __name__ == "__main__":
    raise SystemExit(main())
