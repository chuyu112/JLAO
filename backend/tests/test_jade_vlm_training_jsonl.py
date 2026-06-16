import json
import importlib.util
from pathlib import Path


def _load_vlm_export_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "create_jade_vlm_training_jsonl.py"
    spec = importlib.util.spec_from_file_location("create_jade_vlm_training_jsonl", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vlm_training_jsonl_exports_multimodal_message_record(tmp_path):
    module = _load_vlm_export_module()
    records = [
        {
            "image_path": "jade/a.jpg",
            "text": "直播间补充：阳绿冰种观音吊坠",
            "color": "阳绿",
            "water": "冰种",
            "style": "吊坠",
            "theme": "观音",
            "batch_id": "batch-001",
        }
    ]

    result = module.convert_records(records)
    output = tmp_path / "vlm.jsonl"
    module.write_jsonl(output, result["records"])
    written = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

    assert result["skipped"] == []
    assert written[0]["image"] == "jade/a.jpg"
    assert written[0]["attributes"] == {
        "color": "阳绿",
        "water": "冰种",
        "style": "吊坠",
        "theme": "观音",
    }
    assert written[0]["messages"][0]["content"][0] == {"type": "image", "image": "jade/a.jpg"}
    assert "补充文本" in written[0]["messages"][0]["content"][1]["text"]
    assert json.loads(written[0]["messages"][1]["content"]) == written[0]["attributes"]


def test_vlm_training_jsonl_skips_incomplete_labels_by_default():
    module = _load_vlm_export_module()
    records = [{"image_path": "jade/b.jpg", "color": "蓝水", "water": "", "style": "吊坠", "theme": ""}]

    result = module.convert_records(records)

    assert result["records"] == []
    assert result["skipped"] == [{"index": 0, "reason": "missing_attributes", "missing": ["water", "theme"]}]
