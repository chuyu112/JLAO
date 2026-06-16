import importlib.util
from pathlib import Path


def _load_error_summary_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "summarize_jade_prediction_errors.py"
    spec = importlib.util.spec_from_file_location("summarize_jade_prediction_errors", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prediction_error_summary_counts_confusions_by_attribute():
    module = _load_error_summary_module()
    rows = [
        {
            "image_path": "a.jpg",
            "expected_color": "阳绿",
            "predicted_color": "阳绿",
            "expected_water": "冰种",
            "predicted_water": "糯种",
            "expected_style": "吊坠",
            "predicted_style": "吊坠",
            "expected_theme": "观音",
            "predicted_theme": "佛公",
        },
        {
            "image_path": "b.jpg",
            "expected_color": "蓝水",
            "predicted_color": "晴水",
            "expected_water": "高冰",
            "predicted_water": "",
            "expected_style": "吊坠",
            "predicted_style": "吊坠",
            "expected_theme": "龙牌",
            "predicted_theme": "龙牌",
        },
    ]

    summary = module.summarize_errors(rows)

    assert summary["row_count"] == 2
    assert summary["attributes"]["color"]["error_count"] == 1
    assert summary["attributes"]["water"]["missing_predicted"] == 1
    assert summary["attributes"]["theme"]["confusions"][0] == {"expected": "观音", "predicted": "佛公", "count": 1}
    assert summary["total_errors"] == 4


def test_prediction_error_summary_uses_actual_and_model_aliases():
    module = _load_error_summary_module()
    rows = [{"actual_color": "红翡", "model_color": "黄翡"}]

    summary = module.summarize_errors(rows)

    assert summary["attributes"]["color"]["confusions"] == [{"expected": "红翡", "predicted": "黄翡", "count": 1}]
