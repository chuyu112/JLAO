import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class JadeYoloTrainingConfigTests(unittest.TestCase):
    def test_dataset_yaml_uses_expected_jade_detection_classes(self) -> None:
        from app.services.jade_training_config import JADE_YOLO_CLASS_NAMES, build_jade_dataset_yaml

        yaml_text = build_jade_dataset_yaml("data/jade_yolo")

        self.assertIn("path: data/jade_yolo", yaml_text)
        self.assertIn("0: jade_bangle", yaml_text)
        self.assertIn("13: gourd", yaml_text)
        self.assertEqual(len(JADE_YOLO_CLASS_NAMES), 14)

    def test_all_training_classes_map_to_runtime_jade_attributes(self) -> None:
        from app.services.jade_training_config import JADE_YOLO_CLASS_NAMES
        from app.services.jade_yolo_service import jade_attributes_from_yolo_label

        unmapped = [
            name for name in JADE_YOLO_CLASS_NAMES if jade_attributes_from_yolo_label(name) == ("", "")
        ]

        self.assertEqual(unmapped, [])


if __name__ == "__main__":
    unittest.main()
