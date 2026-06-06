import importlib.util
from pathlib import Path


def _load_smoke_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "create_jade_smoke_images.py"
    spec = importlib.util.spec_from_file_location("create_jade_smoke_images", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_image_renderer_writes_valid_png(tmp_path):
    module = _load_smoke_module()
    sample = module.SMOKE_SAMPLES[0]

    pixels = module.render_sample(sample)
    output = tmp_path / "jade-smoke.png"
    module.write_png(output, width=320, height=320, pixels=pixels)

    data = output.read_bytes()
    assert len(pixels) == 320 * 320
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"IHDR" in data[:32]
    assert data.endswith(b"IEND\xaeB`\x82")
