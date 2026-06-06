from __future__ import annotations

import argparse
import csv
import math
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "real_bangle_bmp_ai20" / "source.png"
DEFAULT_OUTPUT = ROOT / "data" / "real_bangle_bmp_ai20"


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    def clip(self, width: int, height: int) -> "Box":
        return Box(
            max(0.0, min(float(width - 1), self.x1)),
            max(0.0, min(float(height - 1), self.y1)),
            max(0.0, min(float(width - 1), self.x2)),
            max(0.0, min(float(height - 1), self.y2)),
        )

    def to_yolo(self, width: int, height: int) -> tuple[float, float, float, float]:
        cx = (self.x1 + self.x2) / 2 / width
        cy = (self.y1 + self.y2) / 2 / height
        bw = self.width / width
        bh = self.height / height
        return cx, cy, bw, bh


def parse_box(value: str) -> Box:
    parts = [float(item.strip()) for item in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("box must be x1,y1,x2,y2")
    x1, y1, x2, y2 = parts
    if x2 <= x1 or y2 <= y1:
        raise argparse.ArgumentTypeError("box must have x2>x1 and y2>y1")
    return Box(x1, y1, x2, y2)


def parse_crop(value: str) -> tuple[int, int, int, int]:
    parts = [int(item.strip()) for item in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("crop must be left,top,right,bottom")
    left, top, right, bottom = parts
    if right <= left or bottom <= top:
        raise argparse.ArgumentTypeError("crop must have right>left and bottom>top")
    return left, top, right, bottom


def reset_output_dirs(output_dir: Path) -> None:
    for relative in [
        "images/train",
        "labels/train",
        "qa/overlays/train",
    ]:
        path = output_dir / relative
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)


def draw_box(image: Image.Image, box: Box, label: str = "jade_bangle") -> Image.Image:
    preview = image.convert("RGB")
    draw = ImageDraw.Draw(preview, "RGBA")
    line = max(3, round(min(preview.size) * 0.008))
    draw.rectangle([box.x1, box.y1, box.x2, box.y2], outline=(255, 91, 0, 255), width=line)
    draw.rectangle([box.x1, max(0, box.y1 - 28), min(preview.width - 1, box.x1 + 150), box.y1], fill=(255, 91, 0, 210))
    draw.text((box.x1 + 8, max(0, box.y1 - 23)), label, fill=(255, 255, 255, 255))
    return preview


def build_affine(
    width: int,
    height: int,
    rng: random.Random,
) -> tuple[tuple[float, float, float, float, float, float], tuple[float, float, float, float, float, float], dict[str, float]]:
    angle = rng.uniform(-5.0, 5.0)
    scale = rng.uniform(0.94, 1.07)
    tx = rng.uniform(-18.0, 18.0)
    ty = rng.uniform(-24.0, 24.0)
    theta = math.radians(angle)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    cx = width / 2.0
    cy = height / 2.0

    # Forward transform: source pixel -> output pixel.
    a = scale * cos_t
    b = -scale * sin_t
    d = scale * sin_t
    e = scale * cos_t
    c = cx + tx - a * cx - b * cy
    f = cy + ty - d * cx - e * cy

    det = a * e - b * d
    ia = e / det
    ib = -b / det
    id_ = -d / det
    ie = a / det
    ic = -(ia * c + ib * f)
    iff = -(id_ * c + ie * f)

    return (a, b, c, d, e, f), (ia, ib, ic, id_, ie, iff), {
        "angle": angle,
        "scale": scale,
        "tx": tx,
        "ty": ty,
    }


def transform_box(box: Box, matrix: tuple[float, float, float, float, float, float], width: int, height: int) -> Box:
    a, b, c, d, e, f = matrix
    points = [
        (box.x1, box.y1),
        (box.x2, box.y1),
        (box.x2, box.y2),
        (box.x1, box.y2),
    ]
    transformed = [(a * x + b * y + c, d * x + e * y + f) for x, y in points]
    xs = [point[0] for point in transformed]
    ys = [point[1] for point in transformed]
    return Box(min(xs), min(ys), max(xs), max(ys)).clip(width, height)


def add_phone_video_noise(image: Image.Image, box: Box, rng: random.Random) -> Image.Image:
    result = image.convert("RGB")
    result = ImageEnhance.Brightness(result).enhance(rng.uniform(0.82, 1.16))
    result = ImageEnhance.Contrast(result).enhance(rng.uniform(0.88, 1.18))
    result = ImageEnhance.Color(result).enhance(rng.uniform(0.82, 1.22))
    result = ImageEnhance.Sharpness(result).enhance(rng.uniform(0.75, 1.38))

    if rng.random() < 0.38:
        result = result.filter(ImageFilter.GaussianBlur(rng.uniform(0.25, 1.05)))

    if rng.random() < 0.65:
        overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay, "RGBA")
        for _ in range(rng.randint(1, 3)):
            y = rng.uniform(box.y1 + 8, box.y2 - 8)
            x1 = rng.uniform(max(0, box.x1 - 20), min(result.width - 1, box.x1 + box.width * 0.45))
            x2 = rng.uniform(max(x1 + 30, box.x1 + box.width * 0.55), min(result.width - 1, box.x2 + 20))
            draw.line(
                [(x1, y), (x2, y + rng.uniform(-8, 8))],
                fill=(255, 255, 255, rng.randint(26, 70)),
                width=rng.randint(2, 5),
            )
        result = Image.alpha_composite(result.convert("RGBA"), overlay).convert("RGB")

    if rng.random() < 0.35:
        overlay = Image.new("RGBA", result.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay, "RGBA")
        bar_h = rng.randint(26, 48)
        y = rng.randint(int(result.height * 0.55), int(result.height * 0.80))
        draw.rounded_rectangle(
            [rng.randint(4, 20), y, rng.randint(230, 360), y + bar_h],
            radius=8,
            fill=(20, 20, 20, rng.randint(45, 95)),
        )
        result = Image.alpha_composite(result.convert("RGBA"), overlay).convert("RGB")

    if rng.random() < 0.4:
        shift = rng.choice([-10, -6, 6, 10])
        channel = rng.choice([0, 2])
        r, g, b = result.split()
        channels = [r, g, b]
        channels[channel] = ImageChops.offset(channels[channel], shift, 0)
        result = Image.merge("RGB", channels)

    return result


def make_ring_cutout(image: Image.Image, box: Box) -> Image.Image:
    crop = image.crop((round(box.x1), round(box.y1), round(box.x2), round(box.y2))).convert("RGBA")
    width, height = crop.size
    mask = Image.new("L", crop.size, 0)
    draw = ImageDraw.Draw(mask)
    pad_x = round(width * 0.012)
    pad_y = round(height * 0.012)
    draw.ellipse([pad_x, pad_y, width - pad_x, height - pad_y], fill=255)

    # This ring is photographed nearly front-on. The inner hole is slightly low and wide.
    inner = [
        round(width * 0.145),
        round(height * 0.205),
        round(width * 0.855),
        round(height * 0.812),
    ]
    draw.ellipse(inner, fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    crop.putalpha(mask)
    return crop


def erase_source_bangle(image: Image.Image, box: Box, rng: random.Random) -> Image.Image:
    base = image.convert("RGB")
    blurred = base.filter(ImageFilter.GaussianBlur(rng.uniform(18, 34)))
    width, height = base.size
    pad_x = round(box.width * 0.10)
    pad_y = round(box.height * 0.12)
    erase_box = [
        max(0, round(box.x1 - pad_x)),
        max(0, round(box.y1 - pad_y)),
        min(width - 1, round(box.x2 + pad_x)),
        min(height - 1, round(box.y2 + pad_y)),
    ]
    mask = Image.new("L", base.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(erase_box, radius=36, fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(20))
    return Image.composite(blurred, base, mask)


def tint_cutout(cutout: Image.Image, rng: random.Random) -> tuple[Image.Image, str]:
    palettes = [
        ("icy_green", (125, 226, 178), 0.20, 1.05),
        ("yellow_green", (205, 220, 91), 0.34, 1.04),
        ("imperial_green", (20, 172, 94), 0.34, 0.95),
        ("lavender", (188, 150, 224), 0.38, 1.03),
        ("ink_green", (18, 75, 61), 0.32, 0.72),
        ("blue_water", (110, 204, 222), 0.28, 1.03),
    ]
    name, rgb, blend, brightness = rng.choice(palettes)
    alpha = cutout.getchannel("A")
    original = cutout.convert("RGB")
    tinted = Image.blend(original, Image.new("RGB", cutout.size, rgb), rng.uniform(max(0.08, blend - 0.08), blend + 0.08))
    tinted = ImageEnhance.Brightness(tinted).enhance(rng.uniform(brightness * 0.90, brightness * 1.12))
    tinted = ImageEnhance.Contrast(tinted).enhance(rng.uniform(0.92, 1.20))
    tinted = ImageEnhance.Color(tinted).enhance(rng.uniform(0.90, 1.25))
    result = tinted.convert("RGBA")
    result.putalpha(alpha)
    return result, name


def fit_rgba(image: Image.Image, target_width: int) -> Image.Image:
    ratio = target_width / image.width
    target_height = max(1, round(image.height * ratio))
    return image.resize((target_width, target_height), Image.Resampling.LANCZOS)


def paste_random_cutout(
    background: Image.Image,
    cutout: Image.Image,
    rng: random.Random,
) -> tuple[Image.Image, Box, dict[str, float]]:
    width, height = background.size
    for _ in range(20):
        target_width = rng.randint(round(width * 0.50), round(width * 0.90))
        scaled = fit_rgba(cutout, target_width)
        angle = rng.uniform(-15.0, 15.0)
        rotated = scaled.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
        if rotated.width > width - 6:
            rotated = fit_rgba(rotated, width - rng.randint(8, 20))

        min_x = max(-12, -round(rotated.width * 0.06))
        max_x = min(width - rotated.width + 12, width - round(rotated.width * 0.94))
        if max_x < min_x:
            min_x = max(0, width - rotated.width)
            max_x = max(0, width - rotated.width)

        min_y = round(height * 0.23)
        max_y = round(height * 0.74) - rotated.height
        if max_y < min_y:
            min_y = max(0, round(height * 0.18))
            max_y = max(min_y, height - rotated.height - 8)

        x = rng.randint(min_x, max_x)
        y = rng.randint(min_y, max_y)

        layer = Image.new("RGBA", background.size, (0, 0, 0, 0))
        layer.alpha_composite(rotated, (x, y))
        alpha_box = layer.getchannel("A").getbbox()
        if not alpha_box:
            continue
        label_box = Box(*alpha_box).clip(width, height)
        if label_box.width < width * 0.28 or label_box.height < height * 0.13:
            continue
        image = Image.alpha_composite(background.convert("RGBA"), layer).convert("RGB")
        return image, label_box, {
            "angle": angle,
            "scale": target_width / cutout.width,
            "tx": float(x),
            "ty": float(y),
        }
    raise RuntimeError("failed to place cutout inside frame")


def save_jpeg_with_quality(image: Image.Image, path: Path, rng: random.Random) -> None:
    image.save(path, format="JPEG", quality=rng.randint(72, 94), optimize=True)


def make_contact_sheet(paths: list[Path], output_path: Path, thumb_width: int = 180) -> None:
    thumbs: list[Image.Image] = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        ratio = thumb_width / image.width
        thumb = image.resize((thumb_width, max(1, int(image.height * ratio))), Image.Resampling.LANCZOS)
        thumbs.append(thumb)
    cols = 5
    rows = math.ceil(len(thumbs) / cols)
    pad = 8
    thumb_height = max(thumb.height for thumb in thumbs)
    sheet = Image.new("RGB", (cols * thumb_width + (cols + 1) * pad, rows * thumb_height + (rows + 1) * pad), (245, 245, 245))
    for idx, thumb in enumerate(thumbs):
        x = pad + (idx % cols) * (thumb_width + pad)
        y = pad + (idx // cols) * (thumb_height + pad)
        sheet.paste(thumb, (x, y))
    sheet.save(output_path, quality=90)


def write_dataset_yaml(output_dir: Path) -> None:
    yaml_text = "\n".join(
        [
            f"path: {output_dir.resolve().as_posix()}",
            "train: images/train",
            "val: images/train",
            "names:",
            "  0: jade_bangle",
            "",
        ]
    )
    (output_dir / "dataset.yaml").write_text(yaml_text, encoding="utf-8")


def validate_label(box: Box, width: int, height: int) -> None:
    cx, cy, bw, bh = box.to_yolo(width, height)
    values = [cx, cy, bw, bh]
    if not all(0.0 < value <= 1.0 for value in values):
        raise ValueError(f"invalid YOLO values: {values}")
    if box.width < 20 or box.height < 20:
        raise ValueError(f"box too small: {box}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create 20 real livestream jade-bangle YOLO training samples.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--seed", type=int, default=606060)
    parser.add_argument("--crop", type=parse_crop, default=parse_crop("0,34,450,1004"))
    parser.add_argument("--bbox", type=parse_box, default=parse_box("64,337,446,729"))
    parser.add_argument("--preview-only", action="store_true")
    args = parser.parse_args()

    source = Image.open(args.source).convert("RGB")
    crop_left, crop_top, crop_right, crop_bottom = args.crop
    cropped = source.crop((crop_left, crop_top, crop_right, crop_bottom))
    width, height = cropped.size
    source_box = args.bbox.clip(width, height)
    validate_label(source_box, width, height)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    cropped.save(args.output_dir / "source_crop.png")
    draw_box(cropped, source_box).save(args.output_dir / "source_bbox_preview.jpg", quality=92)
    cutout = make_ring_cutout(cropped, source_box)
    cutout.save(args.output_dir / "source_ring_cutout.png")
    write_dataset_yaml(args.output_dir)

    if args.preview_only:
        print(f"source_crop={args.output_dir / 'source_crop.png'}")
        print(f"source_bbox_preview={args.output_dir / 'source_bbox_preview.jpg'}")
        print(f"crop_size={width}x{height}")
        print(f"bbox_xyxy={source_box}")
        print("bbox_yolo=0 " + " ".join(f"{value:.6f}" for value in source_box.to_yolo(width, height)))
        return

    reset_output_dirs(args.output_dir)
    rng = random.Random(args.seed)
    manifest_rows: list[dict[str, str]] = []
    overlay_paths: list[Path] = []

    for idx in range(1, args.count + 1):
        background = erase_source_bangle(cropped, source_box, rng)
        variant_cutout, color_name = tint_cutout(cutout, rng)
        composited, label_box, transform_meta = paste_random_cutout(background, variant_cutout, rng)
        validate_label(label_box, width, height)
        augmented = add_phone_video_noise(composited, label_box, rng)

        stem = f"real_bangle_bmp_ai20_{idx:03d}"
        image_path = args.output_dir / "images" / "train" / f"{stem}.jpg"
        label_path = args.output_dir / "labels" / "train" / f"{stem}.txt"
        overlay_path = args.output_dir / "qa" / "overlays" / "train" / f"{stem}.jpg"
        save_jpeg_with_quality(augmented, image_path, rng)
        cx, cy, bw, bh = label_box.to_yolo(width, height)
        label_path.write_text(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n", encoding="utf-8")
        draw_box(augmented, label_box).save(overlay_path, quality=90)
        overlay_paths.append(overlay_path)
        manifest_rows.append(
            {
                "image": str(image_path.relative_to(args.output_dir)).replace("\\", "/"),
                "label": str(label_path.relative_to(args.output_dir)).replace("\\", "/"),
                "bbox_xyxy": f"{label_box.x1:.1f},{label_box.y1:.1f},{label_box.x2:.1f},{label_box.y2:.1f}",
                "bbox_yolo": f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}",
                "angle": f"{transform_meta['angle']:.3f}",
                "scale": f"{transform_meta['scale']:.3f}",
                "tx": f"{transform_meta['tx']:.3f}",
                "ty": f"{transform_meta['ty']:.3f}",
                "color": color_name,
            }
        )

    with (args.output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)

    make_contact_sheet(overlay_paths, args.output_dir / "preview_train_20.jpg")
    print(f"output_dir={args.output_dir.resolve()}")
    print(f"images={len(list((args.output_dir / 'images' / 'train').glob('*.jpg')))}")
    print(f"labels={len(list((args.output_dir / 'labels' / 'train').glob('*.txt')))}")
    print(f"preview={args.output_dir / 'preview_train_20.jpg'}")
    print(f"dataset_yaml={args.output_dir / 'dataset.yaml'}")


if __name__ == "__main__":
    main()
