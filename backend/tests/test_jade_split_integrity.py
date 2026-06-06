import importlib.util
from pathlib import Path


def _load_integrity_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_jade_split_integrity.py"
    spec = importlib.util.spec_from_file_location("check_jade_split_integrity", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_split_integrity_accepts_disjoint_manifests():
    module = _load_integrity_module()
    train = [{"image_path": "jade/train-a.jpg"}, {"image_path": "jade/train-b.jpg"}]
    eval_rows = [{"image_path": "jade/eval-a.jpg"}, {"image_path": "jade/eval-b.jpg"}]

    summary = module.inspect_integrity(train, eval_rows)

    assert summary["status"] == "ok"
    assert summary["overlap_count"] == 0
    assert summary["train_duplicate_count"] == 0
    assert summary["eval_duplicate_count"] == 0
    assert summary["issues"] == []


def test_split_integrity_reports_overlap_and_duplicates():
    module = _load_integrity_module()
    train = [{"image_path": "jade/shared.jpg"}, {"image_path": "jade/shared.jpg"}]
    eval_rows = [{"image_path": "jade/shared.jpg"}, {"image_path": "jade/eval.jpg"}, {"image_path": "jade/eval.jpg"}]

    summary = module.inspect_integrity(train, eval_rows)

    assert summary["status"] == "failed"
    messages = {issue["message"] for issue in summary["issues"]}
    assert "train/eval overlap" in messages
    assert "duplicate train rows" in messages
    assert "duplicate eval rows" in messages
