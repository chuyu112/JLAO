#!/usr/bin/env python3
"""
实时 YOLO 检测：复用现有 phone_capture_service 截图循环
直接运行即可，不需要改动现有代码。
"""
import asyncio
import cv2
import numpy as np
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ultralytics import YOLO

# ========== 配置 ==========
ROI_X1, ROI_X2 = 0.05, 0.95
ROI_Y1, ROI_Y2 = 0.15, 0.55
AREA_THRESHOLD = 0.15
MODEL_NAME = "yolov8n.pt"
CAPTURE_INTERVAL = 0.2  # 秒，与现有服务一致

# 颜色 (BGR)
COLOR_ORANGE = (0, 165, 255)
COLOR_RED = (0, 0, 255)


async def capture_once():
    """复用 phone_capture_service 的截图逻辑"""
    # 延迟导入避免循环依赖
    from app.services.phone_capture_service import capture_once as _cap
    return await _cap("test_session", None)


def draw_detections(frame, roi_box, detections):
    """在原始帧上画 ROI 红框 + 货品橙框"""
    rx1, ry1, rx2, ry2 = roi_box

    # 画 ROI 红框
    cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), COLOR_RED, 2)
    cv2.putText(frame, "ROI", (rx1 + 5, ry1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_RED, 2)

    # 画检测框
    for det in detections:
        x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
        cv2.rectangle(frame, (x1, y1), (x2, y2), COLOR_ORANGE, 3)

        label = f"{det['name']} {det['conf']:.2f} ({det['ratio']*100:.0f}%)"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw, y1), COLOR_ORANGE, -1)
        cv2.putText(frame, label, (x1, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return frame


async def main():
    print(f"加载模型: {MODEL_NAME}")
    model = YOLO(MODEL_NAME)
    print("模型就绪。按 Q 退出。")

    cv2.namedWindow("YOLO Real-time", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("YOLO Real-time", 540, 960)

    while True:
        # 1. 截图（复用现有服务）
        try:
            snapshot = await capture_once()
            if not snapshot or not snapshot.get("image_path"):
                await asyncio.sleep(0.1)
                continue
        except Exception as e:
            print(f"截图失败: {e}")
            await asyncio.sleep(0.5)
            continue

        # 2. 读取图片
        img_path = snapshot["image_path"]
        frame = cv2.imread(str(img_path))
        if frame is None:
            continue

        h, w = frame.shape[:2]

        # 3. ROI 裁剪
        rx1, rx2 = int(w * ROI_X1), int(w * ROI_X2)
        ry1, ry2 = int(h * ROI_Y1), int(h * ROI_Y2)
        roi = frame[ry1:ry2, rx1:rx2]

        # 4. YOLO 推理
        results = model(roi, verbose=False)

        # 5. 过滤 + 坐标转换
        roi_h, roi_w = roi.shape[:2]
        detections = []

        for box in results[0].boxes:
            bx, by, bw, bh = box.xywh[0].cpu().numpy()
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            cls_name = results[0].names[cls_id]

            ratio = (bw * bh) / (roi_w * roi_h)
            if ratio < AREA_THRESHOLD:
                continue

            # 转回原始画面坐标
            abs_x1 = int(rx1 + bx - bw / 2)
            abs_y1 = int(ry1 + by - bh / 2)
            abs_x2 = int(abs_x1 + bw)
            abs_y2 = int(abs_y1 + bh)

            detections.append({
                "x1": abs_x1, "y1": abs_y1,
                "x2": abs_x2, "y2": abs_y2,
                "conf": conf, "name": cls_name,
                "ratio": ratio,
            })

        # 6. 绘制
        annotated = draw_detections(frame, (rx1, ry1, rx2, ry2), detections)
        cv2.imshow("YOLO Real-time", annotated)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        await asyncio.sleep(CAPTURE_INTERVAL)

    cv2.destroyAllWindows()
    print("已退出")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        cv2.destroyAllWindows()
        print("\n已中断")
