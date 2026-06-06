from __future__ import annotations

import argparse
import csv
import json
import struct
import zlib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "generated_jade_smoke_images"
DEFAULT_MANIFEST = ROOT / "data" / "generated_jade_smoke_manifest.csv"


SMOKE_SAMPLES = [
    {
        "id": "smoke-white-ice-pendant",
        "filename": "smoke-white-ice-pendant.png",
        "background": (246, 250, 248),
        "shape": "pendant",
        "fill": (220, 246, 238),
        "outline": (88, 150, 130),
        "expected": {"color": "白冰", "water": "冰种", "style": "吊坠", "theme": "观音"},
        "text": "白冰冰种观音吊坠",
    },
    {
        "id": "smoke-green-bangle",
        "filename": "smoke-green-bangle.png",
        "background": (242, 248, 242),
        "shape": "bangle",
        "fill": (72, 188, 102),
        "outline": (20, 110, 48),
        "expected": {"color": "阳绿", "water": "糯冰", "style": "手镯", "theme": ""},
        "text": "阳绿糯冰手镯",
    },
    {
        "id": "smoke-blue-dragon-plaque",
        "filename": "smoke-blue-dragon-plaque.png",
        "background": (238, 246, 250),
        "shape": "plaque",
        "fill": (92, 164, 190),
        "outline": (36, 90, 122),
        "expected": {"color": "蓝水", "water": "高冰", "style": "牌子", "theme": "龙牌"},
        "text": "蓝水高冰龙牌",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create synthetic jade smoke images and a labeled manifest.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for generated PNG files.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="CSV manifest output path.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON summary.")
    args = parser.parse_args()

    output_dir = resolve_path(args.output_dir)
    manifest_path = resolve_path(args.manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    for sample in SMOKE_SAMPLES:
        image_path = output_dir / str(sample["filename"])
        pixels = render_sample(sample)
        write_png(image_path, width=320, height=320, pixels=pixels)
        expected = sample["expected"]
        rows.append(
            {
                "id": str(sample["id"]),
                "image": str(image_path.relative_to(ROOT)),
                "text": str(sample["text"]),
                "color": str(expected.get("color", "")),
                "water": str(expected.get("water", "")),
                "style": str(expected.get("style", "")),
                "theme": str(expected.get("theme", "")),
            }
        )

    with manifest_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "image", "text", "color", "water", "style", "theme"])
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "status": "ok",
        "output_dir": str(output_dir),
        "manifest": str(manifest_path),
        "count": len(rows),
        "rows": rows,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else (ROOT / path).resolve()


def render_sample(sample: dict[str, Any], *, width: int = 320, height: int = 320) -> list[tuple[int, int, int]]:
    bg = tuple(sample["background"])
    fill = tuple(sample["fill"])
    outline = tuple(sample["outline"])
    shape = str(sample["shape"])
    pixels = [bg for _ in range(width * height)]
    if shape == "bangle":
        draw_ring(pixels, width, height, 160, 160, 112, 58, fill, outline)
    elif shape == "plaque":
        draw_rounded_rect(pixels, width, height, 86, 48, 234, 272, 24, fill, outline)
        draw_curve(pixels, width, height, outline)
    else:
        draw_teardrop(pixels, width, height, fill, outline)
    add_highlight(pixels, width, height)
    return pixels


def write_png(path: Path, *, width: int, height: int, pixels: list[tuple[int, int, int]]) -> None:
    raw_rows = []
    for y in range(height):
        row = bytearray([0])
        for r, g, b in pixels[y * width : (y + 1) * width]:
            row.extend([r, g, b])
        raw_rows.append(bytes(row))
    raw = b"".join(raw_rows)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw, level=9))
        + png_chunk(b"IEND", b"")
    )


def png_chunk(kind: bytes, data: bytes) -> bytes:
    payload = kind + data
    return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)


def set_pixel(
    pixels: list[tuple[int, int, int]],
    width: int,
    height: int,
    x: int,
    y: int,
    color: tuple[int, int, int],
) -> None:
    if 0 <= x < width and 0 <= y < height:
        pixels[y * width + x] = color


def draw_ring(
    pixels: list[tuple[int, int, int]],
    width: int,
    height: int,
    cx: int,
    cy: int,
    outer: int,
    inner: int,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
) -> None:
    for y in range(height):
        for x in range(width):
            distance = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if inner <= distance <= outer:
                color = outline if distance < inner + 5 or distance > outer - 5 else fill
                set_pixel(pixels, width, height, x, y, color)


def draw_rounded_rect(
    pixels: list[tuple[int, int, int]],
    width: int,
    height: int,
    left: int,
    top: int,
    right: int,
    bottom: int,
    radius: int,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
) -> None:
    for y in range(top, bottom + 1):
        for x in range(left, right + 1):
            dx = max(left + radius - x, 0, x - (right - radius))
            dy = max(top + radius - y, 0, y - (bottom - radius))
            if dx * dx + dy * dy <= radius * radius:
                border = x - left < 5 or right - x < 5 or y - top < 5 or bottom - y < 5
                set_pixel(pixels, width, height, x, y, outline if border else fill)


def draw_teardrop(
    pixels: list[tuple[int, int, int]],
    width: int,
    height: int,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
) -> None:
    for y in range(46, 278):
        for x in range(92, 228):
            top_taper = abs(x - 160) < max(8, int((y - 30) * 0.38))
            oval = ((x - 160) / 74) ** 2 + ((y - 176) / 96) ** 2 <= 1
            if top_taper or oval:
                edge = abs(x - 160) > max(5, int((y - 30) * 0.38) - 5) or ((x - 160) / 70) ** 2 + ((y - 176) / 91) ** 2 > 0.92
                set_pixel(pixels, width, height, x, y, outline if edge else fill)


def draw_curve(pixels: list[tuple[int, int, int]], width: int, height: int, color: tuple[int, int, int]) -> None:
    for t in range(0, 160):
        x = 104 + t
        y = int(116 + 34 * __import__("math").sin(t / 21))
        for dy in range(-2, 3):
            set_pixel(pixels, width, height, x, y + dy, color)


def add_highlight(pixels: list[tuple[int, int, int]], width: int, height: int) -> None:
    for y in range(78, 132):
        for x in range(110, 164):
            if ((x - 132) / 30) ** 2 + ((y - 104) / 18) ** 2 <= 1:
                index = y * width + x
                r, g, b = pixels[index]
                pixels[index] = (min(255, r + 34), min(255, g + 34), min(255, b + 34))


if __name__ == "__main__":
    raise SystemExit(main())
