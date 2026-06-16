from __future__ import annotations

from pathlib import Path
from typing import Any


JADE_YOLO_CLASS_NAMES = [
    "jade_bangle",
    "jade_beads",
    "jade_cabochon",
    "jade_pendant",
    "jade_ring",
    "jade_plaque",
    "pingan_kou",
    "guanyin",
    "buddha",
    "ruyi",
    "leaf",
    "landscape",
    "pixiu",
    "gourd",
    "jade_ornament",
    "caishen",
    "dragon_plaque",
    "fu_gua",
    "fu_dou",
    "jade_necklace",
    "jade_earring",
]

JADE_YOLO_CLASS_DESCRIPTIONS = {
    "jade_bangle": "手镯 / 镯子 / 圆条 / 正圈 / 贵妃镯",
    "jade_beads": "珠串 / 手串 / 佛珠",
    "jade_cabochon": "蛋面 / 戒面 / 鸽子蛋 / 裸石",
    "jade_pendant": "吊坠 / 挂件 / 坠子",
    "jade_ring": "戒指 / 戒托 / 戒圈",
    "jade_plaque": "牌子 / 无事牌 / 山水牌（旧类，标准款式归吊坠）",
    "pingan_kou": "平安扣 / 怀古 / 扣子题材",
    "guanyin": "观音题材",
    "buddha": "佛公 / 弥勒佛题材",
    "ruyi": "如意题材",
    "leaf": "叶子 / 金枝玉叶题材",
    "landscape": "山水题材",
    "pixiu": "貔貅题材",
    "gourd": "葫芦题材",
    "jade_ornament": "摆件 / 把件 / 手把件",
    "caishen": "财神 / 关公 / 武财神题材",
    "dragon_plaque": "龙牌 / 龙纹 / 生肖龙题材",
    "fu_gua": "福瓜题材",
    "fu_dou": "福豆 / 四季豆题材",
    "jade_necklace": "珠链 / 项链",
    "jade_earring": "耳饰 / 耳环 / 耳坠 / 耳钉",
}


def build_jade_dataset_yaml(dataset_root: str | Path = "data/jade_yolo") -> str:
    root = Path(dataset_root).as_posix()
    names = "\n".join(f"  {index}: {name}" for index, name in enumerate(JADE_YOLO_CLASS_NAMES))
    return (
        f"path: {root}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "names:\n"
        f"{names}\n"
    )


def jade_training_manifest(dataset_root: str | Path = "data/jade_yolo") -> dict[str, Any]:
    root = Path(dataset_root)
    return {
        "dataset_root": str(root),
        "dataset_yaml": str(root / "dataset.yaml"),
        "model_output": "models/jade-yolo.pt",
        "classes": [
            {"id": index, "name": name, "description": JADE_YOLO_CLASS_DESCRIPTIONS[name]}
            for index, name in enumerate(JADE_YOLO_CLASS_NAMES)
        ],
        "layout": {
            "train_images": str(root / "images" / "train"),
            "train_labels": str(root / "labels" / "train"),
            "val_images": str(root / "images" / "val"),
            "val_labels": str(root / "labels" / "val"),
            "test_images": str(root / "images" / "test"),
            "test_labels": str(root / "labels" / "test"),
        },
    }
