from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "scripts" / "check_jade_feedback_readiness.py"


def load_checker_module():
    spec = importlib.util.spec_from_file_location("check_jade_feedback_readiness", CHECKER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_feedback_readiness_extracts_corrected_attributes_and_batch_id():
    checker = load_checker_module()
    record = {
        "input": {
            "image": "uploads/jade.jpg",
            "text": "白冰冰种观音吊坠",
            "batch_id": "jade-analysis-batch-test",
        },
        "corrected": {
            "color": "白冰",
            "water": "冰种",
            "style": "吊坠",
            "theme": "观音",
        },
        "prediction": {
            "color": "白冰",
            "water": "糯冰",
            "style": "吊坠",
            "theme": "观音",
        },
        "box": {"x_center": 0.5, "y_center": 0.5, "width": 0.4, "height": 0.6},
    }

    result = checker.inspect_record(1, record)

    assert result["batch_id"] == "jade-analysis-batch-test"
    assert result["has_image"] is True
    assert result["has_text"] is True
    assert result["has_box"] is True
    assert result["corrected"] == {
        "color": "白冰",
        "water": "冰种",
        "style": "吊坠",
        "theme": "观音",
    }
    assert result["prediction"]["water"] == "糯冰"
    assert result["missing_corrected_attributes"] == []


def test_feedback_readiness_extracts_batch_id_from_evidence_texts():
    checker = load_checker_module()
    record = {
        "evidence_texts": ["主播说明", "batch_id=jade-analysis-batch-evidence"],
        "corrected": {
            "color": "蓝水",
            "water": "高冰",
            "style": "吊坠",
            "theme": "龙牌",
        },
    }

    assert checker.feedback_batch_id(record) == "jade-analysis-batch-evidence"


def test_feedback_readiness_accepts_top_level_corrected_and_predicted_fields():
    checker = load_checker_module()
    record = {
        "input": {"batch_id": "jade-analysis-batch-flat", "image": "uploads/flat.jpg"},
        "corrected_color": "阳绿",
        "corrected_water": "糯冰",
        "corrected_style": "手镯",
        "corrected_theme": "如意",
        "predicted_color": "阳绿",
        "predicted_water": "冰种",
        "predicted_style": "手镯",
        "predicted_theme": "",
    }

    result = checker.inspect_record(1, record)

    assert result["corrected"] == {
        "color": "阳绿",
        "water": "糯冰",
        "style": "手镯",
        "theme": "如意",
    }
    assert result["prediction"]["water"] == "冰种"
    assert result["missing_corrected_attributes"] == []
