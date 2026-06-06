from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "scripts" / "check_jade_batch_api.py"


def load_checker_module():
    spec = importlib.util.spec_from_file_location("check_jade_batch_api", CHECKER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_batch_api_manifest_inputs_resolve_images_and_context_text(tmp_path):
    checker = load_checker_module()
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(b"png-placeholder")
    manifest_path = tmp_path / "manifest.csv"
    manifest_path.write_text(
        "image,text,color,water,style,theme\n"
        "sample.png,白冰冰种观音吊坠,白冰,冰种,吊坠,观音\n",
        encoding="utf-8",
    )

    images, texts = checker.load_manifest_inputs(manifest_path)

    assert images == [image_path.resolve()]
    assert texts == ["白冰冰种观音吊坠"]


def test_batch_api_response_inspection_requires_payload_shape():
    checker = load_checker_module()
    response = {
        "batch_id": "jade-analysis-batch-test",
        "items": [
            {
                "color": "白冰",
                "water": "冰种",
                "style": "吊坠",
                "theme": "观音",
                "confidence": 0.74,
                "signals": {"attribute_sources": {"color": {"source": "text"}}},
                "review_flags": [],
            }
        ],
    }

    result = checker.inspect_response(response, expected_count=1, require_all_attributes=True)

    assert result["ok"] is True
    assert result["batch_id"] == "jade-analysis-batch-test"
    assert result["items"][0]["missing_payload_fields"] == []


def test_batch_api_response_inspection_can_block_missing_required_attributes():
    checker = load_checker_module()
    response = {
        "items": [
            {
                "color": "白冰",
                "confidence": 0.2,
                "signals": {"attribute_sources": {"color": {"source": "text"}}},
                "review_flags": ["missing-water-style-theme"],
            }
        ],
    }

    result = checker.inspect_response(response, expected_count=1, require_all_attributes=True)

    assert result["ok"] is False
    assert "invalid-item-payload" in result["blocking_reasons"]
    assert result["items"][0]["missing_attributes"] == ["water", "style", "theme"]
