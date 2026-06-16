import json
import importlib.util
from pathlib import Path


def _load_converter_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "convert_jade_review_queue_to_feedback.py"
    spec = importlib.util.spec_from_file_location("convert_jade_review_queue_to_feedback", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_review_queue_feedback_converter_writes_corrected_attributes(tmp_path):
    module = _load_converter_module()
    rows = [
        {
            "image_path": "jade/a.jpg",
            "text": "直播间描述",
            "color": "阳绿",
            "water": "冰种",
            "style": "吊坠",
            "theme": "观音",
            "batch_id": "batch-001",
            "review_reasons": "low_confidence;review_flags",
        }
    ]

    result = module.convert_records(rows, require_complete=True)
    output = tmp_path / "feedback.jsonl"
    module.write_jsonl(output, result["records"])
    written = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

    assert result["skipped"] == []
    assert written[0]["input"]["image_path"] == "jade/a.jpg"
    assert written[0]["corrected"] == {
        "color": "阳绿",
        "water": "冰种",
        "style": "吊坠",
        "theme": "观音",
    }
    assert "batch_id=batch-001" in written[0]["evidence_texts"]


def test_review_queue_feedback_converter_skips_incomplete_when_required():
    module = _load_converter_module()
    rows = [{"image_path": "jade/b.jpg", "color": "蓝水", "water": "", "style": "吊坠", "theme": ""}]

    result = module.convert_records(rows, require_complete=True)

    assert result["records"] == []
    assert result["skipped"] == [{"index": 0, "missing": ["water", "theme"]}]
