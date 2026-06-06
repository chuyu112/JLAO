from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = ROOT / "scripts" / "check_jade_manifest_readiness.py"


def load_checker_module():
    spec = importlib.util.spec_from_file_location("check_jade_manifest_readiness", CHECKER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_readiness_accepts_expected_attribute_aliases(tmp_path):
    checker = load_checker_module()
    image_path = tmp_path / "sample.jpg"
    image_path.write_bytes(b"not-a-real-image-but-present")
    manifest_path = tmp_path / "manifest.csv"
    manifest_path.write_text(
        "image,expected_color,expected_water,expected_style,expected_theme\n"
        "sample.jpg,白冰,冰种,吊坠,观音\n",
        encoding="utf-8",
    )

    rows = checker.load_manifest(manifest_path)
    result = checker.check_row(1, rows[0], manifest_path)

    assert result["image_exists"] is True
    assert result["attributes"] == {
        "color": "白冰",
        "water": "冰种",
        "style": "吊坠",
        "theme": "观音",
    }
    assert result["missing_attributes"] == []
