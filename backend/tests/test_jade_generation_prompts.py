from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_prompt_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "create_jade_generation_prompts.py"
    spec = importlib.util.spec_from_file_location("create_jade_generation_prompts", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_distractor_prompts_include_hands_body_and_face_without_label_leakage():
    module = _load_prompt_module()

    rows = module.build_rows(4, "data/generated_jade_training_images_distractors", include_distractors=True)
    prompts = "\n".join(row["generation_prompt"].lower() for row in rows[:12])
    negatives = "\n".join(row["negative_prompt"].lower() for row in rows[:12])

    assert "hand" in prompts
    assert "upper body" in prompts or "torso" in prompts
    assert "face" in prompts
    assert "human hand" not in negatives
    assert "face," not in negatives
    assert all(Path(row["image"]).name.startswith("sample-") for row in rows)
    assert all(row["color"] not in Path(row["image"]).name for row in rows)
