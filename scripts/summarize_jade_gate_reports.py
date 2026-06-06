from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PASS_STATUSES = {"ok", "pass", "passed", "success", "succeeded"}
FAIL_STATUSES = {"failed", "fail", "error", "errored"}


def load_report(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def infer_status(payload: Any) -> str:
    if isinstance(payload, dict):
        status = payload.get("status")
        if isinstance(status, str):
            normalized = status.strip().lower()
            if normalized in PASS_STATUSES:
                return "ok"
            if normalized in FAIL_STATUSES:
                return "failed"
        if "returncode" in payload:
            return "ok" if payload.get("returncode") == 0 else "failed"
        steps = payload.get("steps")
        if isinstance(steps, list) and steps:
            return "ok" if all(infer_status(step) == "ok" for step in steps) else "failed"
    if isinstance(payload, list):
        return "ok" if all(infer_status(item) == "ok" for item in payload) else "failed"
    return "unknown"


def count_key(payload: Any, key: str) -> int:
    if isinstance(payload, dict):
        count = 0
        value = payload.get(key)
        if isinstance(value, list):
            count += len(value)
        elif isinstance(value, dict):
            count += len(value)
        for nested in payload.values():
            count += count_key(nested, key)
        return count
    if isinstance(payload, list):
        return sum(count_key(item, key) for item in payload)
    return 0


def summarize_report(path: Path, payload: Any) -> dict[str, Any]:
    return {
        "path": str(path),
        "name": path.stem,
        "status": infer_status(payload),
        "issue_count": count_key(payload, "issues"),
        "error_count": count_key(payload, "errors"),
        "skipped_count": count_key(payload, "skipped"),
    }


def summarize_reports(paths: list[Path]) -> dict[str, Any]:
    reports = [summarize_report(path, load_report(path)) for path in paths]
    failed = [report for report in reports if report["status"] == "failed"]
    unknown = [report for report in reports if report["status"] == "unknown"]
    return {
        "status": "ok" if not failed and not unknown else "failed",
        "report_count": len(reports),
        "failed_count": len(failed),
        "unknown_count": len(unknown),
        "reports": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize jade recognition gate JSON reports.")
    parser.add_argument("--report", action="append", required=True, type=Path, help="Gate JSON report path. Repeatable.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload = summarize_reports(args.report)
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
