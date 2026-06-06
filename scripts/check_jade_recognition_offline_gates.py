from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
TESTS = [
    BACKEND_DIR / "tests" / "test_jade_text_recognition.py",
    BACKEND_DIR / "tests" / "test_jade_model_parsing.py",
    BACKEND_DIR / "tests" / "test_jade_recognition_examples_checker.py",
    BACKEND_DIR / "tests" / "test_jade_manifest_readiness.py",
    BACKEND_DIR / "tests" / "test_jade_batch_api_smoke_helpers.py",
    BACKEND_DIR / "tests" / "test_jade_feedback_readiness.py",
    BACKEND_DIR / "tests" / "test_jade_prediction_results.py",
    BACKEND_DIR / "tests" / "test_jade_smoke_images.py",
    BACKEND_DIR / "tests" / "test_jade_taxonomy_contract.py",
    BACKEND_DIR / "tests" / "test_jade_api_response_contract.py",
    BACKEND_DIR / "tests" / "test_jade_labeling_manifest.py",
    BACKEND_DIR / "tests" / "test_jade_label_distribution.py",
    BACKEND_DIR / "tests" / "test_jade_review_queue.py",
    BACKEND_DIR / "tests" / "test_jade_review_queue_feedback.py",
    BACKEND_DIR / "tests" / "test_jade_manifest_split.py",
    BACKEND_DIR / "tests" / "test_jade_split_integrity.py",
    BACKEND_DIR / "tests" / "test_jade_vlm_training_jsonl.py",
    BACKEND_DIR / "tests" / "test_jade_vlm_training_jsonl_contract.py",
    BACKEND_DIR / "tests" / "test_jade_manifest_images.py",
    BACKEND_DIR / "tests" / "test_jade_prediction_error_summary.py",
    BACKEND_DIR / "tests" / "test_jade_error_review_queue.py",
    BACKEND_DIR / "tests" / "test_jade_confidence_calibration.py",
    BACKEND_DIR / "tests" / "test_jade_gate_report_summary.py",
    BACKEND_DIR / "tests" / "test_jade_source_agreement.py",
    BACKEND_DIR / "tests" / "test_jade_taxonomy_values.py",
]
EXAMPLES = ROOT / "data" / "jade_recognition_examples.jsonl"
EXAMPLE_CHECKER = ROOT / "scripts" / "check_jade_recognition_examples.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run offline jade recognition parser/fusion gates.")
    parser.add_argument("--python", default=sys.executable, help="Python executable used to run pytest/checkers.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print final JSON summary.")
    args = parser.parse_args()

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(BACKEND_DIR) if not existing_pythonpath else f"{BACKEND_DIR}{os.pathsep}{existing_pythonpath}"

    checker_command = [
        args.python,
        str(EXAMPLE_CHECKER),
        "--examples",
        str(EXAMPLES),
    ]
    if args.pretty:
        checker_command.append("--pretty")

    steps = [
        {
            "name": "pytest-offline-gates",
            "command": [args.python, "-m", "pytest", *[str(path) for path in TESTS]],
        },
        {
            "name": "offline-example-checker",
            "command": checker_command,
        },
    ]

    results = [run_step(step, env) for step in steps]
    failed = [result for result in results if result["returncode"] != 0]
    payload = {
        "status": "ok" if not failed else "failed",
        "root": str(ROOT),
        "pythonpath": env["PYTHONPATH"],
        "steps": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if not failed else 1


def run_step(step: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    command = [str(item) for item in step["command"]]
    completed = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
    return {
        "name": step["name"],
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-400_000:],
        "stderr": completed.stderr[-400_000:],
    }


if __name__ == "__main__":
    raise SystemExit(main())
