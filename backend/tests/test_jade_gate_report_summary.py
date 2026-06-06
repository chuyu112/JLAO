import json
import importlib.util
from pathlib import Path


def _load_summary_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "summarize_jade_gate_reports.py"
    spec = importlib.util.spec_from_file_location("summarize_jade_gate_reports", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gate_report_summary_accepts_all_ok_reports(tmp_path):
    module = _load_summary_module()
    first = tmp_path / "offline.json"
    second = tmp_path / "api.json"
    first.write_text(json.dumps({"status": "ok", "issues": []}), encoding="utf-8")
    second.write_text(json.dumps({"steps": [{"returncode": 0}, {"status": "passed"}]}), encoding="utf-8")

    summary = module.summarize_reports([first, second])

    assert summary["status"] == "ok"
    assert summary["report_count"] == 2
    assert summary["failed_count"] == 0
    assert [report["status"] for report in summary["reports"]] == ["ok", "ok"]


def test_gate_report_summary_fails_failed_or_unknown_reports(tmp_path):
    module = _load_summary_module()
    failed = tmp_path / "failed.json"
    unknown = tmp_path / "unknown.json"
    failed.write_text(json.dumps({"status": "failed", "issues": [{"message": "bad"}]}), encoding="utf-8")
    unknown.write_text(json.dumps({"message": "no status"}), encoding="utf-8")

    summary = module.summarize_reports([failed, unknown])

    assert summary["status"] == "failed"
    assert summary["failed_count"] == 1
    assert summary["unknown_count"] == 1
    assert summary["reports"][0]["issue_count"] == 1
