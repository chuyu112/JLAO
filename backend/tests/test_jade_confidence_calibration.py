import importlib.util
from pathlib import Path


def _load_calibration_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "summarize_jade_confidence_calibration.py"
    spec = importlib.util.spec_from_file_location("summarize_jade_confidence_calibration", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_confidence_calibration_groups_accuracy_by_bucket():
    module = _load_calibration_module()
    rows = [
        {
            "confidence": "0.91",
            "expected_color": "阳绿",
            "predicted_color": "阳绿",
            "expected_water": "冰种",
            "predicted_water": "冰种",
            "expected_style": "吊坠",
            "predicted_style": "吊坠",
            "expected_theme": "观音",
            "predicted_theme": "观音",
        },
        {
            "confidence": "0.42",
            "expected_color": "蓝水",
            "predicted_color": "晴水",
            "expected_water": "高冰",
            "predicted_water": "糯种",
            "expected_style": "牌子",
            "predicted_style": "牌子",
            "expected_theme": "龙牌",
            "predicted_theme": "佛公",
        },
    ]

    summary = module.summarize_calibration(rows, bucket_size=0.1)

    assert summary["row_count"] == 2
    assert summary["buckets"]["0.90-1.00"]["complete_accuracy"] == 1.0
    assert summary["buckets"]["0.40-0.50"]["attribute_accuracy"]["style"] == 1.0
    assert summary["buckets"]["0.40-0.50"]["attribute_accuracy"]["color"] == 0.0


def test_confidence_calibration_tracks_missing_confidence():
    module = _load_calibration_module()
    rows = [{"expected_color": "红翡", "predicted_color": "红翡"}]

    summary = module.summarize_calibration(rows)

    assert summary["missing_confidence"] == 1
    assert summary["buckets"]["missing"]["row_count"] == 1
