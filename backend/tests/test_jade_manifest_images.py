import importlib.util
from pathlib import Path


def _load_images_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_jade_manifest_images.py"
    spec = importlib.util.spec_from_file_location("check_jade_manifest_images", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_images_accepts_existing_relative_paths(tmp_path):
    module = _load_images_module()
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    (image_dir / "jade-a.jpg").write_bytes(b"placeholder")
    records = [{"image_path": "images/jade-a.jpg"}]

    summary = module.inspect_images(records, base_dir=tmp_path)

    assert summary["status"] == "ok"
    assert summary["present_count"] == 1
    assert summary["missing_count"] == 0
    assert summary["empty_count"] == 0


def test_manifest_images_reports_missing_and_empty_paths(tmp_path):
    module = _load_images_module()
    records = [{"image_path": "missing.jpg"}, {"text": "no image"}]

    summary = module.inspect_images(records, base_dir=tmp_path)

    assert summary["status"] == "failed"
    assert summary["missing_count"] == 1
    assert summary["empty_count"] == 1
    messages = {issue["message"] for issue in summary["issues"]}
    assert "image files not found" in messages
    assert "rows without image path" in messages
