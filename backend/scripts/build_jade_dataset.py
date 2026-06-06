#!/usr/bin/env python3
"""auto extract orange box coords -> build YOLO dataset"""
import cv2
import numpy as np
from pathlib import Path

SAMPLE_DIR = Path(r"C:\Users\Administrator\Desktop\sample")
OUTPUT_DIR = Path("data/jade_train")
CLASS_ID = 0


def detect_orange_boxes(image_path):
    img = cv2.imread(str(image_path))
    if img is None:
        return []
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    lower = np.array([10, 100, 100])
    upper = np.array([25, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    ih, iw = img.shape[:2]
    total = ih * iw
    candidates = []

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        ratio = (w * h) / total
        if 0.05 < ratio < 0.85:
            candidates.append({"ratio": ratio, "x": x, "y": y, "w": w, "h": h})

    candidates.sort(key=lambda c: c["ratio"], reverse=True)
    return candidates


def build():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for s in ["train", "val"]:
        (OUTPUT_DIR / "images" / s).mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "labels" / s).mkdir(parents=True, exist_ok=True)

    annotated = sorted(SAMPLE_DIR.glob("*-*.png"))
    print(f"found {len(annotated)} annotated images\n")

    for i, img_path in enumerate(annotated):
        img = cv2.imread(str(img_path))
        ih, iw = img.shape[:2]

        boxes = detect_orange_boxes(img_path)
        if not boxes:
            print(f"  WARN {img_path.name} -> no orange box detected")
            continue

        box = boxes[0]
        x, y, w, h = box["x"], box["y"], box["w"], box["h"]

        xc = (x + w / 2) / iw
        yc = (y + h / 2) / ih
        nw = w / iw
        nh = h / ih

        split = "train" if i < len(annotated) * 0.8 else "val"

        dst_img = OUTPUT_DIR / "images" / split / f"jade_{i:03d}.jpg"
        cv2.imwrite(str(dst_img), img)

        dst_label = OUTPUT_DIR / "labels" / split / f"jade_{i:03d}.txt"
        with open(dst_label, "w") as f:
            f.write(f"{CLASS_ID} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}\n")

        print(f"  OK {img_path.name} -> {split}, box=({x},{y},{w},{h}), ratio={box['ratio']*100:.1f}%")

    yaml = f"""path: {OUTPUT_DIR.absolute().as_posix()}
train: images/train
val: images/val
nc: 1
names:
  0: jade
"""
    (OUTPUT_DIR / "data.yaml").write_text(yaml)

    n_train = len(list((OUTPUT_DIR / "images" / "train").glob("*")))
    n_val = len(list((OUTPUT_DIR / "images" / "val").glob("*")))
    print(f"\ndataset ready: {OUTPUT_DIR}")
    print(f"  train: {n_train}")
    print(f"  val: {n_val}")


if __name__ == "__main__":
    build()
