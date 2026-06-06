import csv
import importlib.util
from pathlib import Path


def _load_error_queue_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "create_jade_error_review_queue.py"
    spec = importlib.util.spec_from_file_location("create_jade_error_review_queue", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_error_review_queue_exports_prediction_mismatches(tmp_path):
    module = _load_error_queue_module()
    rows = [
        {
            "image_path": "jade/a.jpg",
            "expected_color": "阳绿",
            "predicted_color": "阳绿",
            "expected_water": "冰种",
            "predicted_water": "糯种",
            "expected_style": "吊坠",
            "predicted_style": "吊坠",
            "expected_theme": "观音",
            "predicted_theme": "佛公",
            "batch_id": "eval-001",
        },
        {
            "image_path": "jade/b.jpg",
            "expected_color": "蓝水",
            "predicted_color": "蓝水",
            "expected_water": "高冰",
            "predicted_water": "高冰",
            "expected_style": "牌子",
            "predicted_style": "牌子",
            "expected_theme": "龙牌",
            "predicted_theme": "龙牌",
        },
    ]

    queue = module.queue_rows(rows)
    output = tmp_path / "errors.csv"
    module.write_queue(output, queue)
    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        written = list(csv.DictReader(handle))

    assert len(queue) == 1
    assert written[0]["image_path"] == "jade/a.jpg"
    assert written[0]["predicted_water"] == "糯种"
    assert written[0]["water"] == "冰种"
    assert written[0]["error_attributes"] == "water;theme"
    assert written[0]["batch_id"] == "eval-001"


def test_error_review_queue_can_include_missing_expected_labels():
    module = _load_error_queue_module()
    rows = [{"image_path": "jade/c.jpg", "predicted_color": "红翡"}]

    assert module.queue_rows(rows) == []
    assert module.queue_rows(rows, include_missing_expected=True)[0]["error_attributes"] == "color"
