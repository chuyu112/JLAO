from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "jade_generation_prompts.csv"
DEFAULT_JSONL = ROOT / "data" / "jade_generation_prompts.jsonl"
DEFAULT_IMAGE_DIR = "data/generated_jade_training_images"
DEFAULT_LIVEROOM_OUTPUT = ROOT / "data" / "jade_liveroom_generation_prompts.csv"
DEFAULT_LIVEROOM_JSONL = ROOT / "data" / "jade_liveroom_generation_prompts.jsonl"
DEFAULT_LIVEROOM_IMAGE_DIR = "data/generated_jade_liveroom_training_images"


COLORS: dict[str, str] = {
    "帝王绿": "deep vivid imperial emerald green, saturated but natural jade color",
    "阳绿": "bright positive emerald green, clean vivid green jade tone",
    "辣绿": "intense spicy green, high saturation, bold green jade tone",
    "苹果绿": "fresh apple green, bright yellow-green jade tone",
    "豆绿": "muted bean green, softer gray-green jade tone",
    "绿色": "natural medium green jade tone",
    "蓝水": "blue-water jade, cool blue green with darker watery tone",
    "晴水": "qingshui jade, pale clear blue-green like calm water",
    "油青": "oily green jade, grayish dark green with oily cast",
    "紫罗兰": "lavender purple jade, soft violet tone",
    "春带彩": "chun dai cai jade, visible purple and green color zones in one piece",
    "白冰": "white ice jade, milky white to icy white with translucency",
    "无色": "colorless jade, clear transparent to near-white without visible color",
    "白底青": "white-base-green jade, white ground with distinct green patches",
    "飘花": "floating-flower jade, pale base with blue or green floating streaks",
    "洒金": "sajin jade, pale jade base with scattered golden yellow speckles",
    "黄翡": "yellow jadeite, warm honey yellow to golden yellow tone",
    "冰黄": "icy yellow jadeite, clear translucent yellow with icy luster",
    "墨翠": "black-green jadeite, very dark green to black, glossy",
    "红翡": "red jadeite, red to reddish orange jade tone",
    "多彩": "multicolor jadeite, three or more visible jade color areas",
}


WATERS: dict[str, str] = {
    "玻璃种": "glass-type jade, very high transparency, glass-like clarity, minimal grain",
    "高冰": "high-ice jade, very translucent, strong luster, fine clean texture",
    "冰种": "ice-type jade, translucent and clean, visible watery depth",
    "糯冰": "waxy-ice jade, semi-translucent, slightly cloudy but still icy",
    "糯种": "waxy jade, soft cloudy translucency, fine waxy texture",
    "豆种": "bean-type jade, low translucency, visible granular texture",
}


STYLE_THEMES: list[dict[str, str]] = [
    {"style": "手镯", "theme": "", "subject": "a single complete jade bangle bracelet lying flat, full ring visible"},
    {"style": "手镯", "theme": "", "subject": "a round jade bangle standing slightly upright on a small acrylic rest"},
    {"style": "平安扣", "theme": "", "subject": "a round jade safety buckle pendant, circular disc with a clean central hole"},
    {"style": "珠串", "theme": "", "subject": "a jade bead bracelet, individual polished round beads clearly visible"},
    {"style": "蛋面", "theme": "", "subject": "a loose oval jade cabochon gemstone, domed top, no metal setting"},
    {"style": "戒面", "theme": "", "subject": "a polished oval jade ring-face stone, flatter than a cabochon, no metal setting"},
    {"style": "戒指", "theme": "", "subject": "a jade ring with a jade cabochon mounted on a simple ring band"},
    {"style": "挂件", "theme": "观音", "subject": "a carved jade pendant of Guanyin, full carving visible"},
    {"style": "挂件", "theme": "佛公", "subject": "a carved jade pendant of laughing Buddha, rounded belly visible"},
    {"style": "挂件", "theme": "如意", "subject": "a carved jade ruyi pendant with curved ruyi silhouette"},
    {"style": "挂件", "theme": "叶子", "subject": "a carved jade leaf pendant with leaf veins visible"},
    {"style": "挂件", "theme": "山水", "subject": "a rectangular jade landscape plaque pendant with mountain and water relief carving"},
    {"style": "挂件", "theme": "貔貅", "subject": "a carved jade pixiu pendant, mythical beast silhouette visible"},
    {"style": "挂件", "theme": "葫芦", "subject": "a carved jade gourd pendant with double-lobed gourd shape"},
    {"style": "挂件", "theme": "龙", "subject": "a carved jade dragon plaque pendant with dragon relief visible"},
    {"style": "挂件", "theme": "福瓜", "subject": "a carved jade melon pendant with ribbed melon form"},
    {"style": "挂件", "theme": "无事牌", "subject": "a plain rectangular jade plaque pendant, smooth face, no carved figure"},
    {"style": "吊坠", "theme": "", "subject": "a small simple jade drop pendant with polished surface, no figurative carving"},
]


LIGHTING_VARIANTS = [
    "soft daylight product photography, neutral gray background",
    "studio product photo, softbox reflection, matte black background",
    "macro product photography, white acrylic base, clean shadow",
    "jewelry catalog photo, warm side light, beige stone surface",
]


LIVEROOM_VARIANTS = [
    (
        "live-stream jade sales room, a host is talking about the jade item, "
        "upper body and face visible behind the product, one hand holding the jade close to the camera, "
        "soft ring light reflection, display trays in the background"
    ),
    (
        "vertical live-commerce room scene, a female presenter is explaining the jade piece, "
        "face and torso visible but slightly behind focus, both hands presenting the jade under bright studio lights, "
        "blurred shelves of jewelry in the background"
    ),
    (
        "jade livestream selling desk, presenter is speaking while pointing at the item, "
        "one hand and part of the upper body visible, face partially visible at the edge of frame, "
        "phone tripod and softbox reflections in the room"
    ),
    (
        "busy live sales counter, host holding the jade item above a velvet tray, "
        "human hand, wrist, upper body and face visible as natural distractors, "
        "other jade pieces softly blurred in the background"
    ),
]


NEGATIVE_PROMPT = (
    "text, label, caption, watermark, logo, certificate, price tag, QR code, ruler, "
    "human hand, face, cluttered background, multiple unrelated objects, fake plastic look, "
    "overexposed highlights, blurry, cropped object, duplicate object, extra holes, distorted carving"
)

DISTRACTOR_NEGATIVE_PROMPT = (
    "text, label, caption, watermark, logo, certificate, price tag, QR code, ruler, "
    "fake plastic look, overexposed highlights, blurry jade item, cropped jade object, duplicate jade object, "
    "extra holes in jade, distorted carving, deformed hands, extra fingers, distorted facial features"
)


def build_prompt(row: dict[str, str]) -> str:
    color_desc = COLORS[row["color"]]
    water_desc = WATERS[row["water"]]
    light = row["lighting"]
    scene = row.get("scene", "product")
    intro = f"Photorealistic jadeite jewelry product image: {row['subject']}."
    if scene == "liveroom":
        intro = (
            f"Generate one realistic live-stream sales room image: a livestream host is talking about this jade item; "
            f"{row['subject']}. {row['distractor']}."
        )
    return (
        f"{intro} "
        f"Material and color: {color_desc}. "
        f"Water quality: {water_desc}. "
        "The jade object must be the main visual focus, fully visible, sharp focus, realistic polished jade luster, "
        "natural inclusions and texture appropriate for jadeite, no text or labels in the image. "
        f"{light}."
    )


def build_rows(per_color: int, image_dir: str, *, include_distractors: bool = False, scene: str = "product") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    colors = list(COLORS)
    waters = list(WATERS)
    scene = "liveroom" if include_distractors else scene
    for color_index, color in enumerate(colors):
        for item_index in range(per_color):
            global_index = len(rows) + 1
            water = waters[(color_index + item_index) % len(waters)]
            style_theme = STYLE_THEMES[(color_index * per_color + item_index) % len(STYLE_THEMES)]
            lighting = LIGHTING_VARIANTS[(color_index + item_index) % len(LIGHTING_VARIANTS)]
            distractor = LIVEROOM_VARIANTS[(color_index * per_color + item_index) % len(LIVEROOM_VARIANTS)] if scene == "liveroom" else ""
            target_filename = f"sample-{global_index:04d}.png"
            image = str(Path(image_dir) / target_filename).replace("\\", "/")
            labels = {
                "color": color,
                "water": water,
                "style": style_theme["style"],
                "theme": style_theme["theme"],
            }
            row = {
                "id": f"jade-gen-{global_index:04d}",
                "image": image,
                "target_filename": target_filename,
                "color": labels["color"],
                "water": labels["water"],
                "style": labels["style"],
                "theme": labels["theme"],
                "subject": style_theme["subject"],
                "lighting": lighting,
                "scene": scene,
                "distractor": distractor,
                "generation_prompt": "",
                "negative_prompt": DISTRACTOR_NEGATIVE_PROMPT if scene == "liveroom" else NEGATIVE_PROMPT,
                "training_answer_json": json.dumps(labels, ensure_ascii=False, sort_keys=True),
                "split": "val" if global_index % 10 == 0 else "train",
                "batch_id": "jade-synthetic-liveroom-v1" if scene == "liveroom" else "jade-synthetic-v1",
            }
            row["generation_prompt"] = build_prompt(row)
            rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "image",
        "target_filename",
        "color",
        "water",
        "style",
        "theme",
        "subject",
        "lighting",
        "scene",
        "distractor",
        "generation_prompt",
        "negative_prompt",
        "training_answer_json",
        "split",
        "batch_id",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def summarize(rows: list[dict[str, str]]) -> dict[str, Any]:
    summary: dict[str, Any] = {"rows": len(rows), "colors": {}, "waters": {}, "styles": {}, "themes": {}}
    for source, key in [("colors", "color"), ("waters", "water"), ("styles", "style"), ("themes", "theme")]:
        counts: dict[str, int] = {}
        for row in rows:
            value = row[key] or "(none)"
            counts[value] = counts.get(value, 0) + 1
        summary[source] = dict(sorted(counts.items(), key=lambda item: item[0]))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Create balanced prompts for synthetic jade image generation.")
    parser.add_argument("--output", type=Path, help="CSV output path.")
    parser.add_argument("--jsonl", type=Path, help="JSONL output path.")
    parser.add_argument("--image-dir", help="Future neutral image directory written in manifest rows.")
    parser.add_argument("--per-color", type=int, default=12, help="Prompt count per color label.")
    parser.add_argument("--include-distractors", action="store_true", help="Generate livestream room prompts with hands, upper body, and face distractors.")
    parser.add_argument("--scene", choices=["product", "liveroom"], default="product", help="Prompt scene type.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print summary JSON.")
    args = parser.parse_args()

    scene = "liveroom" if args.include_distractors else args.scene
    output = args.output or (DEFAULT_LIVEROOM_OUTPUT if scene == "liveroom" else DEFAULT_OUTPUT)
    jsonl = args.jsonl or (DEFAULT_LIVEROOM_JSONL if scene == "liveroom" else DEFAULT_JSONL)
    image_dir = args.image_dir or (DEFAULT_LIVEROOM_IMAGE_DIR if scene == "liveroom" else DEFAULT_IMAGE_DIR)
    rows = build_rows(args.per_color, image_dir, include_distractors=args.include_distractors, scene=scene)
    write_csv(output, rows)
    write_jsonl(jsonl, rows)
    print(json.dumps({"csv": str(output), "jsonl": str(jsonl), **summarize(rows)}, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
