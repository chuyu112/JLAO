from __future__ import annotations

import argparse
import csv
import json
import math
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import (
    Image,
    ImageChops,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageOps,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "data" / "generated_jade_bangle_gpt_image_100" / "images"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "jade_bangle_composite_200"
WIDTH = 1008
HEIGHT = 1792
CLASS_ID = 0
CLASS_NAME = "jade"


PALETTES = [
    {"name": "apple_green", "base": (64, 170, 96), "dark": (28, 90, 56), "light": (184, 246, 202)},
    {"name": "imperial_green", "base": (24, 132, 65), "dark": (12, 58, 32), "light": (130, 230, 160)},
    {"name": "yellow_honey", "base": (211, 169, 68), "dark": (108, 70, 24), "light": (255, 232, 139)},
    {"name": "lavender_purple", "base": (151, 122, 190), "dark": (82, 58, 124), "light": (225, 207, 246)},
    {"name": "black_ink", "base": (28, 48, 42), "dark": (5, 13, 12), "light": (88, 128, 113)},
    {"name": "icy_white", "base": (198, 228, 218), "dark": (122, 160, 152), "light": (245, 255, 250)},
    {"name": "blue_water", "base": (74, 157, 174), "dark": (34, 83, 96), "light": (183, 237, 245)},
    {"name": "bean_green", "base": (118, 169, 96), "dark": (58, 91, 42), "light": (205, 234, 177)},
    {"name": "dark_green", "base": (20, 88, 54), "dark": (5, 35, 22), "light": (78, 151, 100)},
    {"name": "white_green_flower", "base": (175, 220, 202), "dark": (62, 132, 97), "light": (242, 255, 248)},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create synthetic jade bangle YOLO dataset with exact boxes.")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--test-count", type=int, default=50)
    parser.add_argument("--val-count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260605)
    return parser.parse_args()


def unique_output_dir(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = path.with_name(f"{path.name}_v{index}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not find unique output directory for {path}")


def source_images(path: Path) -> list[Path]:
    files = sorted([p for p in path.glob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}])
    if not files:
        raise FileNotFoundError(f"no source images found under {path}")
    return files


def ensure_dirs(root: Path) -> None:
    for relative in [
        "all/images",
        "all/labels",
        "all/overlays",
        "images/train",
        "images/val",
        "images/test",
        "labels/train",
        "labels/val",
        "labels/test",
        "qa/overlays/train",
        "qa/overlays/val",
        "qa/overlays/test",
    ]:
        (root / relative).mkdir(parents=True, exist_ok=True)


def fit_source(path: Path, rng: random.Random) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image = ImageOps.fit(image, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    image = ImageEnhance.Color(image).enhance(rng.uniform(0.86, 1.08))
    image = ImageEnhance.Contrast(image).enhance(rng.uniform(0.92, 1.08))
    image = ImageEnhance.Brightness(image).enhance(rng.uniform(0.92, 1.05))
    return image.convert("RGBA")


def alpha_composite(base: Image.Image, layer: Image.Image) -> Image.Image:
    return Image.alpha_composite(base.convert("RGBA"), layer.convert("RGBA"))


def rounded_rect(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: tuple[int, ...]) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def draw_display_surface(base: Image.Image, rng: random.Random) -> Image.Image:
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    x1 = rng.randint(18, 70)
    x2 = rng.randint(930, 1000)
    top = rng.randint(300, 390)
    bottom = rng.randint(1210, 1325)
    skew = rng.randint(-35, 35)
    poly = [
        (x1 + rng.randint(-20, 18), top + rng.randint(-35, 30)),
        (x2 + rng.randint(-15, 15), top + skew + rng.randint(-25, 25)),
        (x2 + rng.randint(-30, 10), bottom + rng.randint(-25, 30)),
        (x1 + rng.randint(-10, 30), bottom - skew + rng.randint(-25, 30)),
    ]

    styles = [
        ((242, 239, 229, 244), (220, 216, 205, 110), "paper"),
        ((248, 248, 245, 238), (230, 230, 226, 120), "plastic"),
        ((32, 35, 36, 246), (12, 14, 15, 150), "black_tray"),
        ((231, 237, 242, 238), (205, 215, 224, 130), "foam_board"),
        ((226, 229, 218, 242), (184, 190, 176, 130), "cloth"),
    ]
    fill, shadow, style_name = rng.choice(styles)
    shadow_poly = [(x + rng.randint(12, 24), y + rng.randint(14, 28)) for x, y in poly]
    draw.polygon(shadow_poly, fill=shadow)
    draw.polygon(poly, fill=fill)

    if style_name in {"paper", "foam_board", "plastic"}:
        for _ in range(rng.randint(5, 10)):
            y = rng.randint(top + 80, bottom - 70)
            x_start = rng.randint(x1 + 50, x2 - 250)
            x_end = min(x2 - 45, x_start + rng.randint(130, 430))
            color = rng.choice([(75, 95, 180, 85), (180, 65, 55, 70), (110, 120, 130, 50)])
            draw.line([(x_start, y), (x_end, y + rng.randint(-12, 12))], fill=color, width=rng.randint(3, 6))
        for _ in range(rng.randint(7, 14)):
            x = rng.randint(x1 + 20, x2 - 20)
            y = rng.randint(top + 20, bottom - 20)
            draw.line(
                [(x, y), (x + rng.randint(80, 260), y + rng.randint(-28, 28))],
                fill=(255, 255, 255, rng.randint(30, 80)),
                width=rng.randint(2, 6),
            )
    else:
        for _ in range(rng.randint(16, 28)):
            x = rng.randint(x1, x2)
            y = rng.randint(top, bottom)
            draw.ellipse(
                [x - rng.randint(2, 9), y - rng.randint(1, 6), x + rng.randint(8, 26), y + rng.randint(1, 6)],
                fill=(255, 255, 255, rng.randint(10, 32)),
            )

    return alpha_composite(base, layer)


def channel(value: int) -> int:
    return max(0, min(255, int(value)))


def colorize_noise(size: tuple[int, int], palette: dict[str, Any], rng: random.Random) -> Image.Image:
    noise = Image.effect_noise(size, rng.uniform(42, 78)).convert("L")
    dark = tuple(channel(v + rng.randint(-12, 10)) for v in palette["dark"])
    light = tuple(channel(v + rng.randint(-8, 16)) for v in palette["light"])
    return ImageOps.colorize(noise, dark, light).convert("RGBA")


def make_ring_mask(size: tuple[int, int], thickness: float, rng: random.Random) -> Image.Image:
    scale = 3
    w, h = size
    mask = Image.new("L", (w * scale, h * scale), 0)
    draw = ImageDraw.Draw(mask)
    pad_x = int(w * scale * rng.uniform(0.025, 0.055))
    pad_y = int(h * scale * rng.uniform(0.045, 0.075))
    outer = [pad_x, pad_y, w * scale - pad_x, h * scale - pad_y]
    draw.ellipse(outer, fill=255)

    inner_pad_x = int(w * scale * thickness)
    inner_pad_y = int(h * scale * thickness * rng.uniform(1.02, 1.25))
    inner = [
        outer[0] + inner_pad_x,
        outer[1] + inner_pad_y,
        outer[2] - inner_pad_x,
        outer[3] - inner_pad_y,
    ]
    draw.ellipse(inner, fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(1.0 * scale))
    return mask.resize(size, Image.Resampling.LANCZOS)


def make_bangle_asset(size: tuple[int, int], palette: dict[str, Any], rng: random.Random) -> Image.Image:
    w, h = size
    thickness = rng.uniform(0.14, 0.23)
    mask = make_ring_mask((w, h), thickness, rng)
    texture = colorize_noise((w, h), palette, rng)

    base = Image.new("RGBA", (w, h), (*palette["base"], 255))
    texture = Image.blend(base, texture, rng.uniform(0.42, 0.68))

    stain = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stain)
    for _ in range(rng.randint(10, 18)):
        x = rng.randint(0, w)
        y = rng.randint(0, h)
        rx = rng.randint(max(12, w // 20), max(28, w // 8))
        ry = rng.randint(max(8, h // 20), max(18, h // 7))
        color = rng.choice(
            [
                (*palette["dark"], rng.randint(24, 75)),
                (*palette["light"], rng.randint(16, 55)),
                (255, 255, 255, rng.randint(14, 36)),
            ]
        )
        sd.ellipse([x - rx, y - ry, x + rx, y + ry], fill=color)
    stain = stain.filter(ImageFilter.GaussianBlur(rng.uniform(7, 18)))
    texture = alpha_composite(texture, stain)

    highlight = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(highlight)
    for offset, alpha, width in [(0.05, 115, 4), (0.12, 65, 3), (0.22, 40, 2)]:
        box = [
            int(w * (0.08 + offset)),
            int(h * (0.12 + offset * 0.35)),
            int(w * (0.92 - offset * 0.25)),
            int(h * (0.78 - offset * 0.35)),
        ]
        hd.arc(box, start=rng.randint(184, 218), end=rng.randint(315, 350), fill=(255, 255, 255, alpha), width=width)
    for _ in range(rng.randint(3, 6)):
        x = rng.randint(int(w * 0.15), int(w * 0.85))
        y = rng.randint(int(h * 0.08), int(h * 0.35))
        hd.ellipse([x - 12, y - 4, x + 48, y + 6], fill=(255, 255, 255, rng.randint(45, 110)))
    texture = alpha_composite(texture, highlight)

    edge = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ed = ImageDraw.Draw(edge)
    ed.ellipse([3, 5, w - 4, h - 6], outline=(255, 255, 255, 52), width=max(2, w // 150))
    ed.ellipse([int(w * 0.17), int(h * 0.23), int(w * 0.83), int(h * 0.72)], outline=(20, 45, 38, 50), width=max(2, w // 180))
    texture = alpha_composite(texture, edge)
    texture.putalpha(mask)
    return texture


def adjust_rgba(image: Image.Image, brightness: float, contrast: float, opacity: float) -> Image.Image:
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A").point(lambda p: int(p * opacity))
    rgb = rgba.convert("RGB")
    rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def paste_bangle(base: Image.Image, rng: random.Random, palette: dict[str, Any]) -> dict[str, Any]:
    target_w = rng.randint(320, 690)
    aspect = rng.uniform(0.48, 0.70)
    target_h = int(target_w * aspect)
    asset = make_bangle_asset((target_w, target_h), palette, rng)

    angle = rng.uniform(-34, 34)
    blur = 0.0
    if rng.random() < 0.32:
        blur = rng.uniform(0.35, 1.65)
    asset = adjust_rgba(asset, rng.uniform(0.82, 1.20), rng.uniform(0.86, 1.18), rng.uniform(0.88, 1.0))
    if blur > 0:
        asset = asset.filter(ImageFilter.GaussianBlur(blur))
    asset = asset.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

    max_x = max(1, WIDTH - asset.width - 12)
    max_y = max(1, HEIGHT - asset.height - 190)
    center_x = rng.uniform(0.36, 0.64)
    center_y = rng.uniform(0.41, 0.63)
    x = int(center_x * WIDTH - asset.width / 2)
    y = int(center_y * HEIGHT - asset.height / 2)
    x = max(12, min(max_x, x))
    y = max(230, min(max_y, y))

    shadow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    shadow_asset = Image.new("RGBA", asset.size, (0, 0, 0, 0))
    shadow_alpha = asset.getchannel("A").filter(ImageFilter.GaussianBlur(rng.uniform(8, 17))).point(lambda p: int(p * 0.34))
    shadow_asset.putalpha(shadow_alpha)
    shadow.paste(shadow_asset, (x + rng.randint(5, 18), y + rng.randint(12, 28)), shadow_asset)
    base = alpha_composite(base, shadow)
    base.paste(asset, (x, y), asset)

    full_mask = Image.new("L", (WIDTH, HEIGHT), 0)
    full_mask.paste(asset.getchannel("A"), (x, y))
    return {
        "image": base,
        "mask": full_mask,
        "angle": angle,
        "blur": blur,
        "asset_size": [asset.width, asset.height],
        "paste_xy": [x, y],
    }


def draw_plastic_glare(base: Image.Image, rng: random.Random, box: tuple[int, int, int, int] | None) -> Image.Image:
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    if box:
        left, top, right, bottom = box
        for _ in range(rng.randint(3, 7)):
            y = rng.randint(max(0, top - 80), min(HEIGHT - 1, bottom + 90))
            draw.line(
                [(max(0, left - 180), y), (min(WIDTH, right + 220), y + rng.randint(-35, 35))],
                fill=(255, 255, 255, rng.randint(35, 105)),
                width=rng.randint(3, 8),
            )
    return alpha_composite(base, layer)


def draw_hand_occlusion(
    base: Image.Image,
    occlusion_mask: Image.Image,
    rng: random.Random,
    box: tuple[int, int, int, int] | None,
) -> tuple[Image.Image, Image.Image, str]:
    if box is None or rng.random() > 0.42:
        return base, occlusion_mask, "none"

    left, top, right, bottom = box
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    mask_layer = Image.new("L", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(layer)
    md = ImageDraw.Draw(mask_layer)
    skin = rng.choice([(221, 168, 142, 245), (232, 183, 154, 245), (204, 142, 112, 245)])

    side = rng.choice(["right", "bottom", "left"])
    if side == "right":
        cx = rng.randint(max(0, right - 50), min(WIDTH + 70, right + 150))
        cy = rng.randint(max(0, top + 40), min(HEIGHT, bottom + 120))
        shape = [cx - 90, cy - 40, cx + 180, cy + 110]
        draw.ellipse(shape, fill=skin)
        md.ellipse(shape, fill=255)
        nail = [cx + 40, cy - 28, cx + 115, cy + 20]
    elif side == "left":
        cx = rng.randint(max(-60, left - 120), min(WIDTH, left + 40))
        cy = rng.randint(max(0, top + 30), min(HEIGHT, bottom + 90))
        shape = [cx - 160, cy - 50, cx + 105, cy + 105]
        draw.ellipse(shape, fill=skin)
        md.ellipse(shape, fill=255)
        nail = [cx - 95, cy - 30, cx - 25, cy + 18]
    else:
        cx = rng.randint(max(0, left + 60), min(WIDTH, right - 20))
        cy = rng.randint(max(0, bottom - 15), min(HEIGHT + 60, bottom + 130))
        shape = [cx - 135, cy - 45, cx + 135, cy + 130]
        draw.ellipse(shape, fill=skin)
        md.ellipse(shape, fill=255)
        nail = [cx + 35, cy - 22, cx + 100, cy + 24]

    draw.ellipse(nail, fill=(237, 218, 208, 230))
    md.ellipse(nail, fill=255)
    layer = layer.filter(ImageFilter.GaussianBlur(rng.uniform(0.2, 0.7)))
    mask_layer = mask_layer.filter(ImageFilter.GaussianBlur(0.6))
    return alpha_composite(base, layer), ImageChops.lighter(occlusion_mask, mask_layer), side


def draw_live_ui(
    base: Image.Image,
    rng: random.Random,
    box: tuple[int, int, int, int] | None,
) -> tuple[Image.Image, Image.Image, str]:
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    occlusion = Image.new("L", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(layer)
    md = ImageDraw.Draw(occlusion)

    draw.rectangle([0, 0, WIDTH, 104], fill=(0, 0, 0, rng.randint(75, 122)))
    draw.ellipse([36, 112, 118, 194], fill=(245, 245, 245, 210))
    rounded_rect(draw, (540, 116, 684, 178), 18, (18, 180, 80, 225))
    rounded_rect(draw, (760, 220, 965, 310), 22, (255, 94, 63, 218))

    for i in range(rng.randint(5, 9)):
        y = 730 + i * rng.randint(52, 68) + rng.randint(-8, 10)
        w = rng.randint(230, 410)
        rounded_rect(draw, (34, y, 34 + w, y + rng.randint(34, 48)), 16, (22, 25, 29, rng.randint(92, 138)))
        for line in range(rng.randint(1, 2)):
            yy = y + 12 + line * 15
            draw.line([(60, yy), (34 + w - rng.randint(30, 90), yy)], fill=(255, 255, 255, rng.randint(55, 100)), width=3)

    # Cover old product widgets from the source screenshot so no unlabeled
    # bangle thumbnail remains in the training image.
    draw.rectangle([0, 1288, WIDTH, HEIGHT], fill=(0, 0, 0, 118))
    md.rectangle([0, 1288, WIDTH, HEIGHT], fill=255)

    card_y = rng.randint(1320, 1435)
    card_h = rng.randint(158, 210)
    card = (36, card_y, 760, min(HEIGHT - 120, card_y + card_h))
    rounded_rect(draw, card, 22, (255, 255, 255, 238))
    rounded_rect(draw, (card[0] + 22, card[1] + 24, card[0] + 150, card[3] - 24), 12, (224, 229, 230, 255))
    rounded_rect(draw, (card[2] - 160, card[3] - 70, card[2] - 34, card[3] - 20), 13, (246, 78, 55, 250))
    draw.line([(card[0] + 178, card[1] + 52), (card[2] - 190, card[1] + 52)], fill=(80, 80, 80, 110), width=5)
    draw.line([(card[0] + 178, card[1] + 92), (card[2] - 230, card[1] + 92)], fill=(160, 160, 160, 115), width=5)
    md.rounded_rectangle(card, radius=22, fill=255)

    side_card = (805, rng.randint(1250, 1355), 980, rng.randint(1460, 1560))
    rounded_rect(draw, side_card, 18, rng.choice([(255, 255, 255, 232), (22, 24, 28, 220)]))
    rounded_rect(
        draw,
        (side_card[0] + 18, side_card[1] + 18, side_card[2] - 18, side_card[1] + 100),
        12,
        (210, 215, 216, 250),
    )
    draw.line(
        [(side_card[0] + 22, side_card[1] + 124), (side_card[2] - 22, side_card[1] + 124)],
        fill=(140, 140, 140, 120),
        width=5,
    )
    md.rounded_rectangle(side_card, radius=18, fill=255)

    for i in range(6):
        cx = WIDTH - 70
        cy = 920 + i * 92
        draw.ellipse([cx - 28, cy - 28, cx + 28, cy + 28], fill=(0, 0, 0, 105), outline=(255, 255, 255, 80), width=2)

    detection = "none"
    if box and rng.random() < 0.55:
        left, top, right, bottom = box
        pad = rng.randint(8, 38)
        draw.rectangle(
            [max(0, left - pad), max(0, top - pad), min(WIDTH - 1, right + pad), min(HEIGHT - 1, bottom + pad)],
            outline=(255, 139, 42, rng.randint(135, 210)),
            width=rng.randint(3, 6),
        )
        draw.rectangle(
            [
                rng.randint(14, 50),
                rng.randint(335, 455),
                rng.randint(900, 1000),
                rng.randint(1140, 1285),
            ],
            outline=(230, 35, 45, rng.randint(120, 185)),
            width=rng.randint(3, 5),
        )
        detection = "red_orange"

    return alpha_composite(base, layer), occlusion, detection


def mask_bbox(mask: Image.Image) -> tuple[int, int, int, int] | None:
    binary = mask.point(lambda p: 255 if p > 26 else 0)
    return binary.getbbox()


def mask_area(mask: Image.Image) -> int:
    hist = mask.point(lambda p: 255 if p > 26 else 0).histogram()
    return hist[255]


def yolo_label(box: tuple[int, int, int, int], size: tuple[int, int]) -> tuple[float, float, float, float]:
    left, top, right, bottom = box
    width, height = size
    return (
        ((left + right) / 2) / width,
        ((top + bottom) / 2) / height,
        (right - left) / width,
        (bottom - top) / height,
    )


def quality_score(
    box: tuple[int, int, int, int],
    visible_fraction: float,
    blur: float,
    angle: float,
) -> float:
    left, top, right, bottom = box
    bw = (right - left) / WIDTH
    bh = (bottom - top) / HEIGHT
    area = bw * bh
    center_x = ((left + right) / 2) / WIDTH
    center_y = ((top + bottom) / 2) / HEIGHT
    area_score = max(0.0, 1.0 - abs(area - 0.115) / 0.115)
    center_score = max(0.0, 1.0 - (abs(center_x - 0.50) / 0.38 + abs(center_y - 0.53) / 0.45) / 2)
    blur_score = max(0.0, 1.0 - blur / 2.0)
    angle_score = max(0.0, 1.0 - abs(angle) / 45.0)
    return round(100 * (0.36 * visible_fraction + 0.27 * area_score + 0.17 * center_score + 0.12 * blur_score + 0.08 * angle_score), 3)


def draw_box_overlay(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    left, top, right, bottom = box
    draw.rectangle([left, top, right, bottom], outline=(255, 0, 0), width=6)
    draw.rectangle([left + 4, top + 4, right - 4, bottom - 4], outline=(255, 160, 0), width=4)
    return out


def create_record(source: Path, index: int, variant: int, seed: int, output_dir: Path) -> dict[str, Any]:
    rng = random.Random(seed + index * 1009 + variant * 9176)
    palette = PALETTES[(index * 2 + variant) % len(PALETTES)]
    image = fit_source(source, rng)
    image = draw_display_surface(image, rng)

    pasted = paste_bangle(image, rng, palette)
    image = pasted["image"]
    full_mask = pasted["mask"]
    original_area = max(1, mask_area(full_mask))
    rough_box = mask_bbox(full_mask)

    image = draw_plastic_glare(image, rng, rough_box)
    occlusion_mask = Image.new("L", (WIDTH, HEIGHT), 0)
    image, occlusion_mask, hand = draw_hand_occlusion(image, occlusion_mask, rng, rough_box)
    image, ui_occ, detection = draw_live_ui(image, rng, rough_box)
    occlusion_mask = ImageChops.lighter(occlusion_mask, ui_occ)

    visible_mask = ImageChops.subtract(full_mask, occlusion_mask)
    box = mask_bbox(visible_mask)
    if box is None:
        box = rough_box
        visible_mask = full_mask
    if box is None:
        raise RuntimeError(f"failed to create visible box for generated sample {index}")

    visible_area = mask_area(visible_mask)
    visible_fraction = visible_area / original_area
    label = yolo_label(box, (WIDTH, HEIGHT))
    score = quality_score(box, visible_fraction, pasted["blur"], pasted["angle"])

    stem = f"bangle_comp_{index:03d}_{variant}"
    image_path = output_dir / "all" / "images" / f"{stem}.jpg"
    label_path = output_dir / "all" / "labels" / f"{stem}.txt"
    overlay_path = output_dir / "all" / "overlays" / f"{stem}.jpg"

    image.convert("RGB").save(image_path, quality=92, subsampling=1)
    label_path.write_text(f"{CLASS_ID} {label[0]:.6f} {label[1]:.6f} {label[2]:.6f} {label[3]:.6f}\n", encoding="utf-8")
    draw_box_overlay(image, box).save(overlay_path, quality=88, subsampling=1)

    return {
        "id": stem,
        "source": source.name,
        "source_index": index,
        "variant": variant,
        "split": "",
        "image": str(image_path.relative_to(output_dir)).replace("\\", "/"),
        "label": str(label_path.relative_to(output_dir)).replace("\\", "/"),
        "overlay": str(overlay_path.relative_to(output_dir)).replace("\\", "/"),
        "color": palette["name"],
        "bbox_xyxy": list(box),
        "yolo_label": f"{CLASS_ID} {label[0]:.6f} {label[1]:.6f} {label[2]:.6f} {label[3]:.6f}",
        "visible_fraction": round(visible_fraction, 4),
        "quality_score": score,
        "angle": round(pasted["angle"], 3),
        "blur": round(pasted["blur"], 3),
        "hand_occlusion": hand,
        "detection_overlay": detection,
        "paste_xy": pasted["paste_xy"],
        "asset_size": pasted["asset_size"],
    }


def assign_splits(records: list[dict[str, Any]], test_count: int, val_count: int) -> None:
    by_source: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_source[int(record["source_index"])].append(record)

    source_scores = []
    for source_index, rows in by_source.items():
        avg_score = sum(float(row["quality_score"]) for row in rows) / len(rows)
        min_score = min(float(row["quality_score"]) for row in rows)
        source_scores.append((round(avg_score * 0.72 + min_score * 0.28, 4), source_index))
    source_scores.sort(reverse=True)

    variants_per_source = len(records) // len(by_source)
    test_sources_needed = math.ceil(test_count / variants_per_source)
    val_sources_needed = math.ceil(val_count / variants_per_source)
    test_sources = {source for _, source in source_scores[:test_sources_needed]}
    val_sources = {source for _, source in source_scores[test_sources_needed : test_sources_needed + val_sources_needed]}

    for record in records:
        source_index = int(record["source_index"])
        if source_index in test_sources:
            record["split"] = "test"
        elif source_index in val_sources:
            record["split"] = "val"
        else:
            record["split"] = "train"

    # If counts overshoot because variants_per_source is not exact, trim lowest quality back to train.
    for split, target in [("test", test_count), ("val", val_count)]:
        rows = [row for row in records if row["split"] == split]
        if len(rows) <= target:
            continue
        rows.sort(key=lambda row: float(row["quality_score"]))
        for row in rows[: len(rows) - target]:
            row["split"] = "train"


def copy_split_files(output_dir: Path, records: list[dict[str, Any]]) -> None:
    for record in records:
        split = record["split"]
        stem = record["id"]
        src_image = output_dir / record["image"]
        src_label = output_dir / record["label"]
        src_overlay = output_dir / record["overlay"]
        dst_image = output_dir / "images" / split / f"{stem}.jpg"
        dst_label = output_dir / "labels" / split / f"{stem}.txt"
        dst_overlay = output_dir / "qa" / "overlays" / split / f"{stem}.jpg"
        shutil.copy2(src_image, dst_image)
        shutil.copy2(src_label, dst_label)
        shutil.copy2(src_overlay, dst_overlay)
        record["image"] = str(dst_image.relative_to(output_dir)).replace("\\", "/")
        record["label"] = str(dst_label.relative_to(output_dir)).replace("\\", "/")
        record["overlay"] = str(dst_overlay.relative_to(output_dir)).replace("\\", "/")


def write_manifest(output_dir: Path, records: list[dict[str, Any]]) -> None:
    fields = [
        "id",
        "split",
        "source",
        "source_index",
        "variant",
        "color",
        "quality_score",
        "visible_fraction",
        "angle",
        "blur",
        "hand_occlusion",
        "detection_overlay",
        "bbox_xyxy",
        "yolo_label",
        "image",
        "label",
        "overlay",
    ]
    with (output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in sorted(records, key=lambda item: item["id"]):
            writer.writerow({field: json.dumps(row[field], ensure_ascii=False) if isinstance(row.get(field), list) else row.get(field, "") for field in fields})


def make_contact_sheet(paths: list[Path], out_path: Path, cols: int = 5, cell: tuple[int, int] = (168, 299)) -> None:
    if not paths:
        return
    rows = math.ceil(len(paths) / cols)
    sheet = Image.new("RGB", (cols * cell[0], rows * cell[1]), (18, 20, 22))
    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGB")
        image.thumbnail(cell, Image.Resampling.LANCZOS)
        tile = Image.new("RGB", cell, (18, 20, 22))
        tile.paste(image, ((cell[0] - image.width) // 2, (cell[1] - image.height) // 2))
        sheet.paste(tile, ((index % cols) * cell[0], (index // cols) * cell[1]))
    sheet.save(out_path, quality=90, subsampling=1)


def write_dataset_yaml(output_dir: Path) -> None:
    path = str(output_dir.resolve()).replace("\\", "/")
    text = (
        f"path: {path}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "names:\n"
        f"  {CLASS_ID}: {CLASS_NAME}\n"
    )
    (output_dir / "dataset.yaml").write_text(text, encoding="utf-8")
    (output_dir / "classes.txt").write_text(f"{CLASS_NAME}\n", encoding="utf-8")


def write_summary(output_dir: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    split_counts = Counter(row["split"] for row in records)
    color_counts = Counter(row["color"] for row in records)
    test_color_counts = Counter(row["color"] for row in records if row["split"] == "test")
    summary = {
        "output_dir": str(output_dir.resolve()),
        "total": len(records),
        "splits": dict(sorted(split_counts.items())),
        "colors": dict(sorted(color_counts.items())),
        "test_colors": dict(sorted(test_color_counts.items())),
        "quality": {
            "min": min(row["quality_score"] for row in records),
            "max": max(row["quality_score"] for row in records),
            "avg": round(sum(row["quality_score"] for row in records) / len(records), 3),
            "test_avg": round(
                sum(row["quality_score"] for row in records if row["split"] == "test") / max(1, split_counts["test"]),
                3,
            ),
        },
        "dataset_yaml": str((output_dir / "dataset.yaml").resolve()),
        "manifest": str((output_dir / "manifest.csv").resolve()),
        "preview_test": str((output_dir / "preview_test_50.jpg").resolve()),
        "preview_train_sample": str((output_dir / "preview_train_sample_50.jpg").resolve()),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def validate_records(records: list[dict[str, Any]]) -> None:
    for row in records:
        parts = row["yolo_label"].split()
        if len(parts) != 5:
            raise RuntimeError(f"invalid label columns for {row['id']}")
        values = [float(value) for value in parts[1:]]
        if any(value <= 0 or value > 1 for value in values):
            raise RuntimeError(f"invalid normalized box for {row['id']}: {row['yolo_label']}")


def main() -> int:
    args = parse_args()
    if args.count % len(source_images(args.source_dir)) != 0:
        # The default case is 100 source screenshots x 2 variants = 200.
        pass
    output_dir = unique_output_dir(args.output_dir)
    ensure_dirs(output_dir)

    sources = source_images(args.source_dir)
    variants = max(1, math.ceil(args.count / len(sources)))
    records: list[dict[str, Any]] = []
    created = 0
    for source_index, source in enumerate(sources, start=1):
        for variant in range(1, variants + 1):
            if created >= args.count:
                break
            record = create_record(source, source_index, variant, args.seed, output_dir)
            records.append(record)
            created += 1
        if created >= args.count:
            break

    assign_splits(records, args.test_count, args.val_count)
    copy_split_files(output_dir, records)
    validate_records(records)
    write_manifest(output_dir, records)
    write_dataset_yaml(output_dir)

    test_overlays = [output_dir / row["overlay"] for row in records if row["split"] == "test"]
    train_overlays = [output_dir / row["overlay"] for row in records if row["split"] == "train"]
    test_overlays.sort()
    train_overlays.sort()
    make_contact_sheet(test_overlays[:50], output_dir / "preview_test_50.jpg")
    make_contact_sheet(train_overlays[:50], output_dir / "preview_train_sample_50.jpg")

    summary = write_summary(output_dir, records)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
