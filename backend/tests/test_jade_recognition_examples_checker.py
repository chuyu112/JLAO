from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "scripts" / "check_jade_recognition_examples.py"
EXAMPLES_PATH = ROOT / "data" / "jade_recognition_examples.jsonl"


def load_checker_module():
    spec = importlib.util.spec_from_file_location("check_jade_recognition_examples", CHECKER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_offline_jade_recognition_examples_match_expected_attributes():
    checker = load_checker_module()
    records = [checker.check_example(record) for record in checker.load_jsonl(EXAMPLES_PATH)]

    assert records
    assert all(record["ok"] for record in records), records
