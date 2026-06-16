import importlib.util
from pathlib import Path


def _load_taxonomy_values_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_jade_taxonomy_values.py"
    spec = importlib.util.spec_from_file_location("check_jade_taxonomy_values", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_taxonomy_values_accepts_manifest_prediction_aliases():
    module = _load_taxonomy_values_module()
    records = [
        {
            "expected_color": "阳绿",
            "predicted_water": "冰种",
            "corrected_style": "吊坠",
            "actual_theme": "观音",
        },
        {
            "prediction": {"model_color": "蓝水", "model_water": "高冰"},
            "corrected": {"style": "吊坠", "theme": "龙牌"},
        },
    ]

    summary = module.inspect_values(records)

    assert summary["status"] == "ok"
    assert summary["issues"] == []
    assert summary["counts"]["color"] == {"阳绿": 1, "蓝水": 1}


def test_taxonomy_values_reports_unknown_and_missing_values():
    module = _load_taxonomy_values_module()
    records = [{"color": "绿得很", "water": "冰种"}]

    summary = module.inspect_values(records, allow_empty=False)

    assert summary["status"] == "failed"
    messages = {(issue["attribute"], issue["message"]) for issue in summary["issues"]}
    assert ("color", "value outside jade taxonomy") in messages
    assert ("style", "missing taxonomy value") in messages
    assert ("theme", "missing taxonomy value") in messages
