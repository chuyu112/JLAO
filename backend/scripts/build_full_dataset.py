#!/usr/bin/env python3
"""build dataset: AI images (auto-segment) + real images (orange box), ROI y:15%-60%"""
import cv2
import numpy as np
from pathlib import Path

AI_DIR = Path(r"C:\Users\Administrator\Desktop\AI sample")
REAL_DIR = Path(r"C:\Users\Administrator\Desktop\sample")
OUTPUT_DIR = Path("data/jade_train_v2")
CLASS_ID = 0

ROI_X1, ROI_X2 = 0.05, 0.95
ROI_Y1, ROI_Y2 = 0.15, 0.60
ROI_W = ROI_X2 - ROI_X1  # 0.90
ROI_H = ROI_Y2 - ROI_Y1  # 0.45


def auto_segment_jade(image_path):
    """自动分割翡翠区域"""
    img = cv2.imread(str(image_path))
    if img is None:
        return None
    h, w = img.shape[:2]
    rx1, rx2 = int(w * ROI_X1), int(w * ROI_X2)
    ry1, ry2 = int(h * ROI_Y1), int(h * ROI_Y2)
    roi = img[ry1:ry2, rx1:rx2]
    ih, iw = roi.shape[:2]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # 1. 排除背景：保留中高饱和度区域
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    bg_mask = (s < 30) | (v < 40)  # 低饱和度或低亮度 = 背景

    # 2. 排除肤色
    skin_mask = (
        (hsv[:, :, 0] < 30) &
        (hsv[:, :, 1] > 40) & (hsv[:, :, 1] < 180) &
        (hsv[:, :, 2] > 80) & (hsv[:, :, 2] < 220)
    )

    # 3. 前景掩码：非背景且非肤色
    fg_mask = (~bg_mask) & (~skin_mask)

    # 4. 形态学清理
    kernel = np.ones((7, 7), np.uint8)
    fg_mask = cv2.morphologyEx(fg_mask.astype(np.uint8), cv2.MORPH_CLOSE, kernel)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))

    # 5. 找连通区域
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(fg_mask, connectivity=8)

    candidates = []
    for i in range(1, num_labels):
        x, y, bw, bh, area = stats[i]
        ratio = area / (ih * iw)
        if 0.03 < ratio < 0.85:
            candidates.append({
                "ratio": ratio,
                "x": (x + bw / 2) / iw,
                "y": (y + bh / 2) / ih,
                "w": bw / iw,
                "h": bh / ih,
            })

    if not candidates:
        return None

    # 选面积最大的
    candidates.sort(key=lambda c: c["ratio"], reverse=True)
    return candidates[0]


def detect_orange_box(image_path):
    img = cv2.imread(str(image_path))
    if img is None:
        return None
    h, w = img.shape[:2]
    rx1, rx2 = int(w * ROI_X1), int(w * ROI_X2)
    ry1, ry2 = int(h * ROI_Y1), int(h * ROI_Y2)
    roi_img = img[ry1:ry2, rx1:rx2]

    hsv = cv2.cvtColor(roi_img, cv2.COLOR_BGR2HSV)
    lower = np.array([10, 100, 100])
    upper = np.array([25, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    ih, iw = roi_img.shape[:2]
    candidates = []
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        ratio = (bw * bh) / (ih * iw)
        if 0.03 < ratio < 0.90:
            candidates.append({
                "x": (x + bw / 2) / iw,
                "y": (y + bh / 2) / ih,
                "w": bw / iw,
                "h": bh / ih,
            })
    candidates.sort(key=lambda c: c["w"] * c["h"], reverse=True)
    return candidates[0] if candidates else None


def build():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for s in ["train", "val"]:
        (OUTPUT_DIR / "images" / s).mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "labels" / s).mkdir(parents=True, exist_ok=True)

    all_items = []

    # AI images: auto-segment
    for i, img_path in enumerate(sorted(AI_DIR.glob("*.png"))):
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h, w = img.shape[:2]
        rx1, rx2 = int(w * ROI_X1), int(w * ROI_X2)
        ry1, ry2 = int(h * ROI_Y1), int(h * ROI_Y2)
        roi = img[ry1:ry2, rx1:rx2]

        box = auto_segment_jade(img_path)
        if box:
            all_items.append({
                "img": roi,
                "label": f"{CLASS_ID} {box['x']:.6f} {box['y']:.6f} {box['w']:.6f} {box['h']:.6f}\n",
                "name": f"ai_{i+1:03d}",
            })
        else:
            print(f"WARN: auto-segment failed for {img_path.name}")

    # Real images: orange box
    for i, img_path in enumerate(sorted(REAL_DIR.glob("*-*.png"))):
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h, w = img.shape[:2]
        rx1, rx2 = int(w * ROI_X1), int(w * ROI_X2)
        ry1, ry2 = int(h * ROI_Y1), int(h * ROI_Y2)
        roi = img[ry1:ry2, rx1:rx2]

        box = detect_orange_box(img_path)
        if box:
            all_items.append({
                "img": roi,
                "label": f"{CLASS_ID} {box['x']:.6f} {box['y']:.6f} {box['w']:.6f} {box['h']:.6f}\n",
                "name": f"real_{i+1:03d}",
            })
        else:
            print(f"WARN: no orange box in {img_path.name}")

    n_train = int(len(all_items) * 0.8)
    for idx, item in enumerate(all_items):
        split = "train" if idx < n_train else "val"
        cv2.imwrite(str(OUTPUT_DIR / "images" / split / f"{item['name']}.jpg"), item['img'])
        (OUTPUT_DIR / "labels" / split / f"{item['name']}.txt").write_text(item['label'])
        print(f"  {item['name']} -> {split}")

    (OUTPUT_DIR / "data.yaml").write_text(
        f"path: {OUTPUT_DIR.absolute().as_posix()}\n"
        f"train: images/train\nval: images/val\nnc: 1\nnames:\n  0: jade\n"
    )
    nt = len(list((OUTPUT_DIR / "images" / "train").glob("*")))
    nv = len(list((OUTPUT_DIR / "images" / "val").glob("*")))
    print(f"\ndataset: {OUTPUT_DIR}  train={nt}  val={nv}")


if __name__ == "__main__":
    build()
