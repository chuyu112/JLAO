#!/usr/bin/env python3
"""
透明悬浮窗：在 scrcpy 投屏画面上直接叠加 YOLO 橙色检测框
"""
import tkinter as tk
import threading
import time
import sys
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import ImageGrab
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).parent.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ========== 配置 ==========
MODEL_NAME = str(WORKSPACE_ROOT / "models" / "jade-yolo.pt")
CONF_THRESHOLD = 0.15
MAX_DETECTIONS = 1
AREA_THRESHOLD = 0.15
ROI_X1, ROI_X2 = 0.05, 0.95
ROI_Y1, ROI_Y2 = 0.15, 0.55
UPDATE_MS = 50  # 刷新间隔 50ms = 20fps

try:
    import torch
except Exception:
    torch = None

YOLO_DEVICE = "0" if torch is not None and torch.cuda.is_available() else "cpu"


def _get_adb_device_name():
    """通过 adb 获取设备型号（如 BLK-AL80）"""
    try:
        result = subprocess.run(
            ["adb", "shell", "getprop", "ro.product.model"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_scrcpy_rect():
    """获取 scrcpy 窗口位置和大小"""
    try:
        import pygetwindow as gw
        # 1. 先尝试匹配 'scrcpy' 标题
        wins = gw.getWindowsWithTitle('scrcpy')
        for w in wins:
            if w.width > 200 and w.height > 300:
                return (w.left, w.top, w.width, w.height)

        # 2. 再尝试匹配设备型号（如 BLK-AL80）
        device = _get_adb_device_name()
        if device:
            wins = gw.getWindowsWithTitle(device)
            for w in wins:
                if w.width > 200 and w.height > 300:
                    return (w.left, w.top, w.width, w.height)

        # 3. 最后尝试模糊匹配包含 scrcpy 或设备名的窗口
        for w in gw.getAllWindows():
            if w.width > 200 and w.height > 300:
                title = w.title.lower()
                if 'scrcpy' in title or (device and device.lower() in title):
                    return (w.left, w.top, w.width, w.height)
    except ImportError:
        pass
    return None


def capture_adb():
    """adb 截图"""
    result = subprocess.run(
        ["adb", "exec-out", "screencap", "-p"],
        capture_output=True, timeout=5
    )
    if result.returncode != 0:
        return None
    img = np.frombuffer(result.stdout, dtype=np.uint8)
    return cv2.imdecode(img, cv2.IMREAD_COLOR)


class OverlayWindow:
    def __init__(self, init_rect):
        self.x, self.y, self.w, self.h = init_rect
        self.detections = []
        self.lock = threading.Lock()

        self.root = tk.Tk()
        self.root.geometry(f"{self.w}x{self.h}+{self.x}+{self.y}")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-transparentcolor', 'white')

        self.canvas = tk.Canvas(self.root, bg='white', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def update_loop(self):
        # 检查 scrcpy 窗口是否移动/resize
        new_rect = get_scrcpy_rect()
        if new_rect:
            nx, ny, nw, nh = new_rect
            if abs(nx - self.x) > 5 or abs(ny - self.y) > 5 or abs(nw - self.w) > 5 or abs(nh - self.h) > 5:
                self.x, self.y, self.w, self.h = nx, ny, nw, nh
                self.root.geometry(f"{self.w}x{self.h}+{self.x}+{self.y}")

        self.canvas.delete("all")

        with self.lock:
            dets = list(self.detections)

        for det in dets:
            x1, y1, x2, y2 = det["box"]
            self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline='#FFA500', width=3
            )
            self.canvas.create_text(
                x1 + 4,
                max(10, y1 - 10),
                text=f"jade {det['conf']:.2f} {det['infer_ms']:.1f}ms",
                anchor="w",
                fill="#FFA500",
                font=("Arial", 10, "bold"),
            )

        self.root.after(UPDATE_MS, self.update_loop)

    def set_detections(self, dets):
        with self.lock:
            self.detections = dets

    def run(self):
        self.update_loop()
        self.root.mainloop()


def yolo_loop(overlay, model):
    frame_count = 0
    while True:
        loop_start = time.perf_counter()
        frame = capture_adb()
        if frame is None:
            time.sleep(0.1)
            continue
        capture_ms = (time.perf_counter() - loop_start) * 1000

        h, w = frame.shape[:2]

        # ROI 裁剪
        rx1, rx2 = int(w * ROI_X1), int(w * ROI_X2)
        ry1, ry2 = int(h * ROI_Y1), int(h * ROI_Y2)
        roi = frame[ry1:ry2, rx1:rx2]

        # YOLO 推理
        infer_start = time.perf_counter()
        results = model.predict(
            roi,
            imgsz=640,
            conf=CONF_THRESHOLD,
            max_det=MAX_DETECTIONS,
            device=YOLO_DEVICE,
            verbose=False,
        )
        if torch is not None and YOLO_DEVICE != "cpu" and torch.cuda.is_available():
            torch.cuda.synchronize()
        infer_ms = (time.perf_counter() - infer_start) * 1000

        roi_h, roi_w = roi.shape[:2]
        dets = []

        for box in results[0].boxes:
            bx, by, bw, bh = box.xywh[0].cpu().numpy()
            conf = float(box.conf[0])
            ratio = (bw * bh) / (roi_w * roi_h)
            if ratio < AREA_THRESHOLD:
                continue

            # adb 截图中的绝对坐标
            abs_x1 = rx1 + bx - bw / 2
            abs_y1 = ry1 + by - bh / 2
            abs_x2 = abs_x1 + bw
            abs_y2 = abs_y1 + bh

            # 转换到 scrcpy 窗口坐标
            scale_x = overlay.w / w
            scale_y = overlay.h / h
            sx1 = max(0, abs_x1 * scale_x)
            sy1 = max(0, abs_y1 * scale_y)
            sx2 = min(overlay.w, abs_x2 * scale_x)
            sy2 = min(overlay.h, abs_y2 * scale_y)

            dets.append({
                "box": (sx1, sy1, sx2, sy2),
                "conf": conf,
                "infer_ms": infer_ms,
            })

        overlay.set_detections(dets)
        frame_count += 1
        if frame_count % 10 == 0:
            total_ms = (time.perf_counter() - loop_start) * 1000
            fps = 1000 / total_ms if total_ms > 0 else 0
            print(
                f"[YOLO] frame={frame_count} det={len(dets)} "
                f"capture={capture_ms:.1f}ms infer={infer_ms:.1f}ms "
                f"total={total_ms:.1f}ms fps={fps:.1f} device={YOLO_DEVICE} conf={CONF_THRESHOLD}"
            )
        time.sleep(0.15)


def main():
    rect = get_scrcpy_rect()
    if not rect:
        print("找不到 scrcpy 窗口。请确保 scrcpy 已启动。")
        print("如果缺少 pygetwindow，请运行: pip install pygetwindow")
        return

    print(f"scrcpy 窗口位置: {rect}")
    print("启动透明悬浮窗... 按 Ctrl+C 退出")

    print(f"加载模型: {MODEL_NAME}")
    print(f"YOLO device={YOLO_DEVICE}, conf={CONF_THRESHOLD}, max_det={MAX_DETECTIONS}")
    model = YOLO(MODEL_NAME)
    print("模型就绪")

    overlay = OverlayWindow(rect)

    t = threading.Thread(target=yolo_loop, args=(overlay, model), daemon=True)
    t.start()

    overlay.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已退出")
