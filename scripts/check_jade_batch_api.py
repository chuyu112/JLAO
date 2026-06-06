from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTES = ("color", "water", "style", "theme")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check the jade batch recognition API with real image files.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL.")
    parser.add_argument("--image", action="append", type=Path, help="Image file to upload. Repeatable.")
    parser.add_argument("--manifest", type=Path, help="Optional CSV/JSON/JSONL manifest. Uses image/image_path/path and text columns.")
    parser.add_argument("--text", default="", help="Optional context text sent with the images.")
    parser.add_argument("--require-all-attributes", action="store_true", help="Fail when any item misses color/water/style/theme.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    manifest_images, manifest_texts = load_manifest_inputs(args.manifest) if args.manifest else ([], [])
    images = [resolve_path(path) for path in (args.image or [])] + manifest_images
    if not images:
        print_json({"status": "missing-input", "error": "Provide at least one --image or a --manifest with image rows."}, pretty=args.pretty)
        return 2
    missing = [str(path) for path in images if not path.exists() or not path.is_file()]
    if missing:
        print_json({"status": "missing-images", "missing": missing}, pretty=args.pretty)
        return 2

    url = f"{args.base_url.rstrip('/')}/api/products/jade-analysis/batch"
    try:
        context_text = args.text or "；".join(text for text in manifest_texts if text)
        response = post_multipart(url, images=images, text=context_text)
    except HTTPError as exc:
        print_json(
            {
                "status": "http-error",
                "url": url,
                "code": exc.code,
                "body": exc.read().decode("utf-8", errors="replace")[:4000],
            },
            pretty=args.pretty,
        )
        return 1
    except URLError as exc:
        print_json({"status": "connection-error", "url": url, "error": str(exc.reason)}, pretty=args.pretty)
        return 1

    result = inspect_response(response, expected_count=len(images), require_all_attributes=args.require_all_attributes)
    payload = {
        "status": "ok" if result["ok"] else "failed",
        "url": url,
        "images": [str(path) for path in images],
        "result": result,
        "response": response,
    }
    print_json(payload, pretty=args.pretty)
    return 0 if result["ok"] else 1


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def load_manifest_inputs(path: Path) -> tuple[list[Path], list[str]]:
    manifest_path = resolve_path(path)
    rows = load_manifest_rows(manifest_path)
    images: list[Path] = []
    texts: list[str] = []
    for row in rows:
        image = first_value(row, ("image", "image_path", "path"))
        if image:
            image_path = Path(image)
            if not image_path.is_absolute():
                image_path = (manifest_path.parent / image_path).resolve()
                if not image_path.exists():
                    image_path = (ROOT / image).resolve()
            images.append(image_path)
        text = first_value(row, ("text", "context_text", "description", "title", "name"))
        if text:
            texts.append(text)
    return images, texts


def load_manifest_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                cleaned = line.strip()
                if cleaned:
                    value = json.loads(cleaned)
                    if isinstance(value, dict):
                        rows.append(value)
        return rows
    if suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict) and isinstance(value.get("rows"), list):
            return [row for row in value["rows"] if isinstance(row, dict)]
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def first_value(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = clean(row.get(key))
        if value:
            return value
    return ""


def post_multipart(url: str, *, images: list[Path], text: str) -> dict[str, Any]:
    boundary = f"----jlao-jade-{uuid.uuid4().hex}"
    body = build_multipart_body(boundary, images=images, text=text)
    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8", errors="replace")
    value = json.loads(raw)
    return value if isinstance(value, dict) else {"raw": value}


def build_multipart_body(boundary: str, *, images: list[Path], text: str) -> bytes:
    chunks: list[bytes] = []
    if text:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                b'Content-Disposition: form-data; name="text"\r\n\r\n',
                text.encode("utf-8"),
                b"\r\n",
            ]
        )
    for image in images:
        mime_type = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="files"; filename="{image.name}"\r\n'
                    f"Content-Type: {mime_type}\r\n\r\n"
                ).encode("utf-8"),
                image.read_bytes(),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks)


def inspect_response(response: dict[str, Any], *, expected_count: int, require_all_attributes: bool) -> dict[str, Any]:
    items = response.get("items") if isinstance(response.get("items"), list) else []
    item_results = [inspect_item(index, item, require_all_attributes=require_all_attributes) for index, item in enumerate(items)]
    blocking_reasons: list[str] = []
    if len(items) != expected_count:
        blocking_reasons.append("unexpected-item-count")
    failed_items = [item for item in item_results if not item["ok"]]
    if failed_items:
        blocking_reasons.append("invalid-item-payload")
    return {
        "ok": not blocking_reasons,
        "expected_count": expected_count,
        "actual_count": len(items),
        "batch_id": str(response.get("batch_id") or ""),
        "blocking_reasons": blocking_reasons,
        "items": item_results,
    }


def inspect_item(index: int, item: Any, *, require_all_attributes: bool) -> dict[str, Any]:
    source = item if isinstance(item, dict) else {}
    missing_payload_fields = [key for key in ["confidence", "signals"] if key not in source]
    attributes = {key: clean(source.get(key)) for key in ATTRIBUTES}
    missing_attributes = [key for key, value in attributes.items() if not value]
    if require_all_attributes:
        missing_payload_fields.extend(missing_attributes)
    return {
        "index": index,
        "ok": not missing_payload_fields,
        "attributes": attributes,
        "confidence": source.get("confidence"),
        "has_attribute_sources": bool(((source.get("signals") or {}).get("attribute_sources") if isinstance(source.get("signals"), dict) else {})),
        "review_flags": source.get("review_flags") or [],
        "missing_attributes": missing_attributes,
        "missing_payload_fields": missing_payload_fields,
    }


def clean(value: Any) -> str:
    return str(value or "").strip()


def print_json(payload: dict[str, Any], *, pretty: bool) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None))


if __name__ == "__main__":
    raise SystemExit(main())
