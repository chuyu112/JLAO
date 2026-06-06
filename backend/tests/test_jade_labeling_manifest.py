import csv
import importlib.util
from pathlib import Path


def _load_manifest_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "create_jade_labeling_manifest.py"
    spec = importlib.util.spec_from_file_location("create_jade_labeling_manifest", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_labeling_manifest_contains_required_jade_columns(tmp_path):
    module = _load_manifest_module()
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    (image_dir / "b.webp").write_bytes(b"placeholder")
    (image_dir / "a.jpg").write_bytes(b"placeholder")
    (image_dir / "ignore.txt").write_text("not an image", encoding="utf-8")
    output = tmp_path / "manifest.csv"

    images = module.discover_images(image_dir)
    rows = module.manifest_rows(images, relative_to=tmp_path, batch_id="batch-001")
    module.write_manifest(output, rows)

    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        written = list(reader)

    assert reader.fieldnames == module.FIELDNAMES
    assert [row["image_path"] for row in written] == ["images\\a.jpg", "images\\b.webp"]
    assert {row["batch_id"] for row in written} == {"batch-001"}
    assert all(row["color"] == row["water"] == row["style"] == row["theme"] == "" for row in written)
