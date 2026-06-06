import csv
import importlib.util
from pathlib import Path


def _load_split_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "split_jade_manifest.py"
    spec = importlib.util.spec_from_file_location("split_jade_manifest", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_split_is_stable_and_marks_split_column(tmp_path):
    module = _load_split_module()
    records = [
        {"image_path": f"jade/{index}.jpg", "color": "阳绿", "water": "冰种", "style": "吊坠", "theme": "观音"}
        for index in range(12)
    ]

    first = module.split_records(records, eval_ratio=0.35, salt="fixed", require_complete=True)
    second = module.split_records(records, eval_ratio=0.35, salt="fixed", require_complete=True)

    assert first["summary"] == second["summary"]
    assert [row["image_path"] for row in first["train"]] == [row["image_path"] for row in second["train"]]
    assert [row["image_path"] for row in first["eval"]] == [row["image_path"] for row in second["eval"]]
    assert all(row["split"] == "train" for row in first["train"])
    assert all(row["split"] == "eval" for row in first["eval"])
    assert first["summary"]["train_count"] + first["summary"]["eval_count"] == 12

    output = tmp_path / "train.csv"
    module.write_csv(output, first["train"], module.fieldnames_for(first["train"] + first["eval"]))
    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        written = list(csv.DictReader(handle))
    assert "split" in written[0]


def test_manifest_split_skips_incomplete_rows_when_required():
    module = _load_split_module()
    records = [
        {"image_path": "complete.jpg", "color": "阳绿", "water": "冰种", "style": "吊坠", "theme": "观音"},
        {"image_path": "missing.jpg", "color": "阳绿", "water": "", "style": "吊坠", "theme": ""},
    ]

    result = module.split_records(records, require_complete=True)

    assert result["summary"]["skipped_count"] == 1
    assert result["skipped"] == [{"index": 1, "reason": "incomplete_labels"}]
    assert result["summary"]["train_count"] + result["summary"]["eval_count"] == 1
