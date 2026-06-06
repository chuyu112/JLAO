from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jade_multimodal_service import analyze_jade_image, analyze_jade_text, merge_jade_analysis
from app.services.jade_review_flags_service import jade_analysis_review_flags
from app.services.jade_yolo_service import get_yolo_runtime_status


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze one jade sample image and optional anchor transcript text.")
    parser.add_argument("--image", default="", help="sample image path")
    parser.add_argument("--text", default="", help="anchor speech text")
    parser.add_argument("--text-file", default="", help="UTF-8 text file containing anchor speech")
    parser.add_argument("--output", default="", help="optional JSON output path")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    args = parser.parse_args()

    text = args.text
    if args.text_file:
        text_path = resolve_path(args.text_file)
        if not text_path.exists():
            print(f"text file not found: {text_path}", file=sys.stderr)
            return 2
        text = text_path.read_text(encoding="utf-8").strip()

    analyses = []
    image_path = None
    if args.image:
        image_path = resolve_path(args.image)
        if not image_path.exists():
            print(f"image not found: {image_path}", file=sys.stderr)
            return 2
        analyses.append(analyze_jade_image(image_path))
    if text.strip():
        analyses.append(analyze_jade_text(text))
    if not analyses:
        print("provide --image, --text, or --text-file", file=sys.stderr)
        return 2

    result = merge_jade_analysis(*analyses) if len(analyses) > 1 else analyses[0]
    payload = analysis_to_payload(result)
    payload["input"] = {
        "image": str(image_path) if image_path else "",
        "text": text,
    }
    payload["runtime"] = {
        "yolo": get_yolo_runtime_status(),
    }
    output_text = json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output_path = resolve_path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text + "\n", encoding="utf-8")
    print(output_text)
    return 0


def resolve_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else (ROOT / candidate).resolve()


def analysis_to_payload(analysis) -> dict[str, Any]:
    return {
        "name": analysis.full_name(),
        "attributes": {
            "color": analysis.color,
            "water": analysis.water,
            "style": analysis.style,
            "theme": analysis.theme,
            "size": analysis.size,
            "price": analysis.price,
        },
        "confidence": analysis.confidence,
        "evidence": {
            "images": analysis.evidence_image_paths,
            "texts": analysis.evidence_texts,
            "detections": analysis.detections,
        },
        "signals": analysis.signals,
        "review_flags": jade_analysis_review_flags(analysis),
    }


if __name__ == "__main__":
    raise SystemExit(main())
