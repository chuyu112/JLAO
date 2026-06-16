import importlib.util
from pathlib import Path


def _load_distribution_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "check_jade_label_distribution.py"
    spec = importlib.util.spec_from_file_location("check_jade_label_distribution", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_label_distribution_accepts_complete_labeled_manifest():
    module = _load_distribution_module()
    records = [
        {"color": "阳绿", "water": "冰种", "style": "吊坠", "theme": "观音"},
        {"color": "蓝水", "water": "高冰", "style": "吊坠", "theme": "龙牌"},
    ]

    summary = module.inspect_distribution(records, min_labeled=2, min_distinct_per_attribute=2)

    assert summary["status"] == "ok"
    assert summary["complete_rows"] == 2
    assert summary["distributions"]["color"]["distinct_count"] == 2
    assert summary["issues"] == []


def test_label_distribution_reports_sparse_labels():
    module = _load_distribution_module()
    records = [
        {"color": "阳绿", "water": "", "style": "吊坠", "theme": ""},
        {"color": "阳绿", "water": "", "style": "", "theme": ""},
    ]

    summary = module.inspect_distribution(records, min_labeled=2, min_distinct_per_attribute=2)

    assert summary["status"] == "failed"
    messages = {(issue["attribute"], issue["message"]) for issue in summary["issues"]}
    assert ("color", "not enough distinct labels") in messages
    assert ("water", "not enough labeled rows") in messages
    assert ("theme", "not enough labeled rows") in messages
