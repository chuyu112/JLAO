from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "scripts" / "check_jade_prediction_results.py"


def load_checker_module():
    spec = importlib.util.spec_from_file_location("check_jade_prediction_results", CHECKER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prediction_results_summary_computes_coverage_and_accuracy():
    checker = load_checker_module()
    rows = [
        {
            "predicted_color": "白冰",
            "predicted_water": "冰种",
            "predicted_style": "吊坠",
            "predicted_theme": "观音",
            "expected_color": "白冰",
            "expected_water": "冰种",
            "expected_style": "吊坠",
            "expected_theme": "观音",
        },
        {
            "predicted_color": "蓝水",
            "predicted_water": "",
            "predicted_style": "牌子",
            "predicted_theme": "龙牌",
            "expected_color": "晴水",
            "expected_water": "高冰",
            "expected_style": "牌子",
            "expected_theme": "龙牌",
        },
    ]

    summary = checker.summarize(rows)

    assert summary["count"] == 2
    assert summary["complete_prediction_rows"] == 1
    assert summary["complete_expected_rows"] == 2
    assert summary["attributes"]["color"]["coverage"] == 1.0
    assert summary["attributes"]["color"]["accuracy"] == 0.5
    assert summary["attributes"]["water"]["coverage"] == 0.5
    assert summary["attributes"]["water"]["accuracy"] == 0.5
    assert summary["attributes"]["style"]["accuracy"] == 1.0
    assert summary["attributes"]["theme"]["accuracy"] == 1.0


def test_prediction_results_value_helpers_support_fallback_columns():
    checker = load_checker_module()
    row = {
        "color": "阳绿",
        "actual_water": "糯冰",
        "label_style": "手镯",
        "corrected_theme": "如意",
    }

    assert checker.predicted_value(row, "color") == "阳绿"
    assert checker.predicted_value(row, "water") == "糯冰"
    assert checker.expected_value(row, "style") == "手镯"
    assert checker.expected_value(row, "theme") == "如意"
