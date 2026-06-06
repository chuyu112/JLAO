import importlib.util
from pathlib import Path


def _load_agreement_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "summarize_jade_source_agreement.py"
    spec = importlib.util.spec_from_file_location("summarize_jade_source_agreement", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_agreement_summarizes_conflicts_against_final_attributes():
    module = _load_agreement_module()
    records = [
        {
            "image_path": "jade/a.jpg",
            "color": "阳绿",
            "water": "冰种",
            "style": "吊坠",
            "theme": "观音",
            "sources": {
                "text": {"color": "阳绿", "water": "冰种", "style": "吊坠", "theme": "观音"},
                "vlm": {"color": "晴水", "water": "糯种", "style": "吊坠", "theme": "佛公"},
            },
        }
    ]

    summary = module.summarize_agreement(records)

    assert summary["source_counts"] == {"text": 1, "vlm": 1}
    assert summary["attribute_conflicts"] == {"color": 1, "water": 1, "theme": 1}
    assert summary["source_conflicts"] == {"vlm": 3}
    assert summary["conflict_examples"][0]["conflicts"][0]["source"] == "vlm"


def test_source_agreement_reads_nested_analysis_and_source_list():
    module = _load_agreement_module()
    records = [
        {
            "analysis": {
                "color": "蓝水",
                "water": "高冰",
                "style": "牌子",
                "theme": "龙牌",
                "signals": [
                    {"source": "yolo", "style": "牌子", "theme": "龙牌"},
                    {"source": "text", "color": "蓝水", "water": "冰种"},
                ],
            }
        }
    ]

    summary = module.summarize_agreement(records)

    assert summary["source_counts"] == {"yolo": 1, "text": 1}
    assert summary["attribute_conflicts"] == {"water": 1}
