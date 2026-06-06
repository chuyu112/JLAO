import io
import sys
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class JadeSampleApiTests(unittest.TestCase):
    def setUp(self) -> None:
        from app.api.products import router

        app = FastAPI()
        app.include_router(router, prefix="/api/products")
        self.client = TestClient(app)

    def test_sample_analysis_api_accepts_text_only(self) -> None:
        response = self.client.post(
            "/api/products/jade-analysis/sample",
            data={"text": "这件白冰冰种观音，高 45mm，宽 28mm，报价 6800"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["attributes"]["color"], "白冰")
        self.assertEqual(payload["attributes"]["water"], "冰种")
        self.assertEqual(payload["attributes"]["theme"], "观音")
        self.assertEqual(payload["attributes"]["price"], 6800)
        self.assertEqual(payload["input"]["text"], "这件白冰冰种观音，高 45mm，宽 28mm，报价 6800")

    def test_sample_analysis_api_accepts_image_and_text(self) -> None:
        import cv2
        import numpy as np

        image = np.full((100, 100, 3), (180, 215, 175), dtype=np.uint8)
        cv2.circle(image, (50, 50), 32, (150, 230, 145), -1)
        ok, encoded = cv2.imencode(".jpg", image)
        self.assertTrue(ok)

        response = self.client.post(
            "/api/products/jade-analysis/sample",
            data={"text": "糯冰珠串，单珠约 8mm"},
            files={"file": ("sample.jpg", io.BytesIO(encoded.tobytes()), "image/jpeg")},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["attributes"]["color"])
        self.assertEqual(payload["attributes"]["style"], "珠串")
        self.assertIn("8mm", payload["attributes"]["size"])
        self.assertTrue(payload["input"]["image"].startswith("/uploads/jade-samples/"))
        self.assertTrue(payload["input"]["image"].endswith(".jpg"))
        self.assertTrue(payload["evidence"]["images"])
        self.assertTrue(payload["evidence"]["texts"])

    def test_sample_analysis_api_requires_image_or_text(self) -> None:
        response = self.client.post("/api/products/jade-analysis/sample", data={"text": ""})

        self.assertEqual(response.status_code, 400)
        self.assertIn("请上传图片或填写主播讲解文本", response.text)

    def test_sample_feedback_api_records_corrected_jade_attributes(self) -> None:
        response = self.client.post(
            "/api/products/jade-analysis/feedback",
            json={
                "input": {"image": "/uploads/jade-samples/sample.jpg", "text": "主播讲解"},
                "predicted": {"color": "白冰", "water": "冰种", "style": "", "theme": "观音"},
                "corrected": {"color": "晴水", "water": "糯冰", "style": "吊坠", "theme": "观音"},
                "evidence": {"images": ["/uploads/jade-samples/sample.jpg"], "texts": ["主播讲解"]},
                "confidence": 0.72,
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["id"].startswith("jade-feedback-"))

    def test_sample_feedback_api_requires_at_least_one_correction(self) -> None:
        response = self.client.post(
            "/api/products/jade-analysis/feedback",
            json={"corrected": {"color": "", "water": "", "style": "", "theme": ""}},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("请至少填写一个人工校正字段", response.text)


if __name__ == "__main__":
    unittest.main()
