import importlib.util
from pathlib import Path


def _load_contract_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_jade_vlm_training_jsonl.py"
    spec = importlib.util.spec_from_file_location("check_jade_vlm_training_jsonl", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_vlm_training_jsonl_contract_accepts_complete_record():
    module = _load_contract_module()
    records = [
        {
            "image": "jade/a.jpg",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": "jade/a.jpg"},
                        {"type": "text", "text": "识别颜色种水样式题材"},
                    ],
                },
                {
                    "role": "assistant",
                    "content": '{"color":"阳绿","water":"冰种","style":"吊坠","theme":"观音"}',
                },
            ],
        }
    ]

    summary = module.inspect_records(records)

    assert summary["status"] == "ok"
    assert summary["issues"] == []
    assert summary["records"][0]["attributes"] == {
        "color": "阳绿",
        "water": "冰种",
        "style": "吊坠",
        "theme": "观音",
    }


def test_vlm_training_jsonl_contract_reports_missing_image_and_attributes():
    module = _load_contract_module()
    records = [
        {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "识别"}]},
                {"role": "assistant", "content": '{"color":"蓝水","water":"","style":"牌子","theme":""}'},
            ]
        }
    ]

    summary = module.inspect_records(records)

    assert summary["status"] == "failed"
    messages = {issue["message"] for issue in summary["issues"]}
    assert "missing image" in messages
    assert "missing user image content" in messages
    assert "missing assistant attributes" in messages
