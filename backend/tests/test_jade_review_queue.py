import csv
import importlib.util
from pathlib import Path


def _load_review_queue_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "create_jade_review_queue.py"
    spec = importlib.util.spec_from_file_location("create_jade_review_queue", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_review_queue_selects_low_confidence_missing_and_flagged_rows(tmp_path):
    module = _load_review_queue_module()
    records = [
        {
            "image_path": "a.jpg",
            "analysis": {"color": "阳绿", "water": "冰种", "style": "吊坠", "theme": "观音", "confidence": 0.91},
        },
        {
            "image_path": "b.jpg",
            "analysis": {"color": "蓝水", "water": "", "style": "牌子", "theme": "龙牌", "confidence": 0.52},
            "review_flags": ["missing_water"],
            "batch_id": "batch-001",
        },
    ]

    rows = module.queue_rows(records, min_confidence=0.65)

    assert len(rows) == 1
    assert rows[0]["image_path"] == "b.jpg"
    assert rows[0]["color"] == "蓝水"
    assert "missing_water" in rows[0]["review_reasons"]
    assert "low_confidence" in rows[0]["review_reasons"]
    assert "review_flags" in rows[0]["review_reasons"]
    assert rows[0]["batch_id"] == "batch-001"

    output = tmp_path / "review.csv"
    module.write_queue(output, rows)
    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert written[0]["image_path"] == "b.jpg"


def test_review_queue_include_all_keeps_clean_rows():
    module = _load_review_queue_module()
    records = [
        {"analysis": {"color": "阳绿", "water": "冰种", "style": "吊坠", "theme": "观音", "confidence": 0.95}}
    ]

    rows = module.queue_rows(records, include_all=True)

    assert len(rows) == 1
    assert rows[0]["review_reasons"] == ""
