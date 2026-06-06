import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class JadeSampleCliTests(unittest.TestCase):
    def test_cli_analyzes_text_without_starting_live_capture(self) -> None:
        command = [
            sys.executable,
            str(ROOT / "scripts" / "analyze_jade_sample.py"),
            "--text",
            "这件白冰冰种观音，高 45mm，宽 28mm，报价 6800",
        ]

        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["attributes"]["color"], "白冰")
        self.assertEqual(payload["attributes"]["water"], "冰种")
        self.assertEqual(payload["attributes"]["theme"], "观音")
        self.assertEqual(payload["attributes"]["price"], 6800)
        self.assertEqual(payload["input"]["text"], "这件白冰冰种观音，高 45mm，宽 28mm，报价 6800")

    def test_cli_rejects_missing_image_path(self) -> None:
        command = [
            sys.executable,
            str(ROOT / "scripts" / "analyze_jade_sample.py"),
            "--image",
            "tmp/not-a-real-jade-image.jpg",
        ]

        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("image not found", result.stderr)

    def test_cli_analyzes_image_and_text_together(self) -> None:
        import cv2
        import numpy as np

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            image = np.full((100, 100, 3), (180, 215, 175), dtype=np.uint8)
            cv2.circle(image, (50, 50), 32, (150, 230, 145), -1)
            cv2.imwrite(str(temp_path), image)
            command = [
                sys.executable,
                str(ROOT / "scripts" / "analyze_jade_sample.py"),
                "--image",
                str(temp_path),
                "--text",
                "糯冰珠串，单珠约 8mm",
            ]

            result = subprocess.run(
                command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["attributes"]["color"])
            self.assertEqual(payload["attributes"]["style"], "珠串")
            self.assertIn("8mm", payload["attributes"]["size"])
            self.assertTrue(payload["evidence"]["images"])
            self.assertTrue(payload["evidence"]["texts"])
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
