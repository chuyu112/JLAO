import importlib.util
from pathlib import Path


def _load_contract_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_jade_api_response_contract.py"
    spec = importlib.util.spec_from_file_location("check_jade_api_response_contract", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_api_response_contract_accepts_batch_results():
    module = _load_contract_module()
    payload = {
        "results": [
            {
                "color": "阳绿",
                "water": "冰种",
                "style": "吊坠",
                "theme": "观音",
                "confidence": 0.91,
                "signals": {"text": ["阳绿冰种观音吊坠"]},
                "review_flags": [],
            }
        ]
    }

    summary = module.inspect_response(payload, require_all_attributes=True)

    assert summary["status"] == "ok"
    assert summary["count"] == 1
    assert summary["issues"] == []


def test_api_response_contract_reports_missing_core_fields():
    module = _load_contract_module()
    payload = {"results": [{"color": "阳绿", "confidence": "high"}]}

    summary = module.inspect_response(payload, require_all_attributes=True)

    assert summary["status"] == "failed"
    messages = {issue["message"] for issue in summary["issues"]}
    assert "missing result fields" in messages
    assert "missing attribute keys" in messages
    assert "confidence must be numeric" in messages


def test_api_response_contract_accepts_nested_analysis_fields():
    module = _load_contract_module()
    payload = {
        "data": [
            {
                "analysis": {
                    "color": "蓝水",
                    "water": "高冰",
                    "style": "牌子",
                    "theme": "龙牌",
                    "confidence": 0.86,
                    "signals": {"vlm": ["蓝水高冰龙牌"]},
                    "review_flags": ["low_light"],
                }
            }
        ]
    }

    summary = module.inspect_response(payload, require_all_attributes=True)

    assert summary["status"] == "ok"
    assert summary["results"][0]["attributes"] == {
        "color": "蓝水",
        "water": "高冰",
        "style": "牌子",
        "theme": "龙牌",
    }
    assert summary["results"][0]["has_confidence"] is True
    assert summary["results"][0]["has_signals"] is True
    assert summary["results"][0]["has_review_flags"] is True
