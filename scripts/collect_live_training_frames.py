from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEEDBACK_PATH = ROOT / "data" / "jade_feedback.jsonl"
DEFAULT_OUTPUT_ROOT = ROOT / "uploads" / "jade-training-real"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect real livestream frames for jade YOLO annotation and training."
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--username", default="operator")
    parser.add_argument("--password", default="jlao123")
    parser.add_argument("--session-id", default="", help="Existing live session ID. Defaults to the first session or creates one.")
    parser.add_argument("--source", choices=["phone-once", "latest-frame"], default="phone-once")
    parser.add_argument("--serial", default="", help="ADB device serial for phone-once mode.")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--duration", type=int, default=3600)
    parser.add_argument("--dedup-threshold", type=int, default=8)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--feedback-path", type=Path, default=DEFAULT_FEEDBACK_PATH)
    parser.add_argument("--no-feedback", action="store_true", help="Only save images and manifest; do not append annotation tasks.")
    args = parser.parse_args()

    api_base = args.api_base.rstrip("/")
    token = login(api_base, args.username, args.password)
    session_id = args.session_id.strip() or ensure_session(api_base, token)

    batch_id = datetime.now().strftime("live-real-%Y%m%d-%H%M%S")
    output_dir = resolve_path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_ROOT / batch_id
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "manifest.csv"
    records_path = output_dir / "feedback_records.jsonl"
    hashes: list[str] = []
    records: list[dict[str, Any]] = []
    rows: list[dict[str, str]] = []
    saved = 0
    attempts = 0
    deadline = time.time() + max(1, args.duration)

    print(json.dumps({
        "status": "collecting",
        "session_id": session_id,
        "source": args.source,
        "target_count": args.count,
        "output_dir": str(output_dir),
    }, ensure_ascii=False))

    while saved < args.count and time.time() < deadline:
        attempts += 1
        try:
            snapshot = capture_snapshot(api_base, token, session_id, args.source, args.serial)
            image_bytes = download_snapshot_image(api_base, token, snapshot)
            duplicate, image_hash = is_duplicate(image_bytes, hashes, threshold=args.dedup_threshold)
            if duplicate:
                print(f"[{attempts}] duplicate skipped")
                time.sleep(max(0.2, args.interval))
                continue

            saved += 1
            filename = f"real_{saved:04d}.jpg"
            image_path = images_dir / filename
            save_jpeg(image_bytes, image_path)
            hashes.append(image_hash)
            if len(hashes) > 300:
                hashes = hashes[-180:]

            record = build_feedback_record(
                image_path=image_path,
                batch_id=batch_id,
                source_snapshot=snapshot,
                image_hash=image_hash,
            )
            records.append(record)
            rows.append({
                "image": relative_to_root(image_path),
                "batch_id": batch_id,
                "feedback_id": record["id"],
                "source_frame_id": str(snapshot.get("id") or snapshot.get("last_frame_id") or ""),
                "source_image": str(snapshot.get("image_path") or ""),
                "hash": image_hash,
                "needs_annotation": "1",
            })
            print(f"[{attempts}] saved {saved}/{args.count}: {filename}")
        except Exception as exc:
            print(f"[{attempts}] capture failed: {exc}")
        time.sleep(max(0.2, args.interval))

    write_manifest(manifest_path, rows)
    write_jsonl(records_path, records)
    if records and not args.no_feedback:
        append_feedback(resolve_path(args.feedback_path), records)

    print(json.dumps({
        "status": "ok" if saved else "empty",
        "session_id": session_id,
        "attempts": attempts,
        "saved": saved,
        "manifest": str(manifest_path),
        "feedback_records": str(records_path),
        "feedback_appended": 0 if args.no_feedback else len(records),
        "next": "Open http://127.0.0.1:5173/annotate and draw boxes for these samples.",
    }, ensure_ascii=False, indent=2))
    return 0 if saved else 2


def login(api_base: str, username: str, password: str) -> str:
    response = requests.post(
        f"{api_base}/api/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    response.raise_for_status()
    token = response.json().get("token")
    if not token:
        raise RuntimeError("login response did not include token")
    return str(token)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def ensure_session(api_base: str, token: str) -> str:
    response = requests.get(f"{api_base}/api/sessions", headers=auth_headers(token), timeout=10)
    response.raise_for_status()
    sessions = response.json()
    if isinstance(sessions, list) and sessions:
        return str(sessions[0]["id"])

    created = requests.post(
        f"{api_base}/api/sessions",
        headers=auth_headers(token),
        json={
            "title": "真实直播截图采集",
            "live_room_name": "浅玩翡翠-2号店",
            "platform": "视频号",
            "anchor_name": "主播",
            "operator_name": "场控",
        },
        timeout=10,
    )
    created.raise_for_status()
    session_id = str(created.json()["id"])
    requests.post(f"{api_base}/api/sessions/{session_id}/start", headers=auth_headers(token), timeout=10).raise_for_status()
    return session_id


def capture_snapshot(api_base: str, token: str, session_id: str, source: str, serial: str) -> dict[str, Any]:
    if source == "phone-once":
        response = requests.post(
            f"{api_base}/api/sessions/{session_id}/phone-capture/once",
            headers=auth_headers(token),
            json={"serial": serial, "interval_seconds": 0.2},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    response = requests.get(
        f"{api_base}/api/sessions/{session_id}/frames",
        headers=auth_headers(token),
        timeout=10,
    )
    response.raise_for_status()
    frames = response.json()
    if not frames:
        raise RuntimeError("no frames available; start video capture first")
    return frames[0]


def download_snapshot_image(api_base: str, token: str, snapshot: dict[str, Any]) -> bytes:
    image_path = str(snapshot.get("image_path") or "")
    if not image_path:
        raise RuntimeError("snapshot has no image_path")
    image_url = image_path if image_path.startswith("http") else f"{api_base}{image_path}"
    separator = "&" if "?" in image_url else "?"
    response = requests.get(f"{image_url}{separator}token={token}", timeout=20)
    response.raise_for_status()
    return response.content


def perceptual_hash(image_bytes: bytes) -> str:
    with Image.open(io.BytesIO(image_bytes)) as image:
        gray = image.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    average = sum(pixels) / len(pixels)
    bits = "".join("1" if pixel > average else "0" for pixel in pixels)
    return hex(int(bits, 2))[2:].zfill(16)


def hamming_distance(left: str, right: str) -> int:
    return bin(int(left, 16) ^ int(right, 16)).count("1")


def is_duplicate(image_bytes: bytes, hashes: list[str], *, threshold: int) -> tuple[bool, str]:
    image_hash = perceptual_hash(image_bytes)
    return any(hamming_distance(image_hash, existing) <= threshold for existing in hashes), image_hash


def save_jpeg(image_bytes: bytes, path: Path) -> None:
    with Image.open(io.BytesIO(image_bytes)) as image:
        rgb = image.convert("RGB")
        rgb.save(path, format="JPEG", quality=90, optimize=True)


def build_feedback_record(
    *,
    image_path: Path,
    batch_id: str,
    source_snapshot: dict[str, Any],
    image_hash: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    image_ref = public_upload_ref(image_path)
    return {
        "id": f"jade-live-real-{uuid.uuid4().hex[:12]}",
        "created_at": now,
        "input": {
            "image": image_ref,
            "batch_id": batch_id,
            "source_frame_id": str(source_snapshot.get("id") or ""),
            "source_image": str(source_snapshot.get("image_path") or ""),
            "image_hash": image_hash,
        },
        "predicted": {},
        "corrected": {"color": "", "water": "", "style": "", "theme": ""},
        "evidence": {"images": [image_ref], "texts": [], "detections": []},
        "confidence": 0.0,
        "source": "live-real-capture",
        "attribute_sources": {},
        "needs_review": True,
        "review_status": "pending",
        "review_reason": "needs-human-yolo-box",
        "training": {
            "suggested_classes": [],
            "yolo_ready": False,
            "requires_manual_box": True,
            "box_mode": "",
        },
    }


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["image", "batch_id", "feedback_id", "source_frame_id", "source_image", "hash", "needs_annotation"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def append_feedback(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def resolve_path(path: Path | None) -> Path:
    if path is None:
        raise ValueError("path is required")
    return path if path.is_absolute() else ROOT / path


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def public_upload_ref(path: Path) -> str:
    try:
        relative = path.resolve().relative_to((ROOT / "uploads").resolve())
        return "/uploads/" + str(relative).replace("\\", "/")
    except ValueError:
        return relative_to_root(path)


if __name__ == "__main__":
    raise SystemExit(main())
