#!/usr/bin/env python3
"""
自动收集直播间多器型样本
用法：python scripts/collect_jade_samples.py --session-id xxx --duration 7200
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

# ============ 配置 ============

# 截图保存目录
SAMPLES_DIR = Path(__file__).resolve().parents[1] / "data" / "jade_samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# 去重间隔（秒）
DEDUP_SECONDS = 5

# 截图间隔（秒）
CAPTURE_INTERVAL = 0.5

# API 基础地址
API_BASE = "http://127.0.0.1:8000"


# ============ 核心逻辑 ============

def get_session_id() -> str:
    """获取当前活跃的 session_id"""
    try:
        resp = requests.get(f"{API_BASE}/api/sessions", timeout=5)
        sessions = resp.json()
        if sessions:
            return sessions[0]["id"]
    except Exception:
        pass
    raise RuntimeError("无法获取 session_id，请确保后端服务已启动并有活跃会话")


def capture_frame(session_id: str) -> dict[str, Any]:
    """截图并获取 YOLO 检测结果"""
    try:
        # 1. 获取当前帧图片
        frames_resp = requests.get(f"{API_BASE}/api/sessions/{session_id}/frames", timeout=10)
        frames = frames_resp.json()

        if not frames:
            return {"success": False, "reason": "no_frames"}

        # 取最新一帧
        latest_frame = frames[0]
        image_url = latest_frame.get("image_path", "")

        if not image_url:
            return {"success": False, "reason": "no_image_path"}

        # 2. 获取 YOLO 检测结果
        detections = latest_frame.get("jade_detections", [])

        return {
            "success": True,
            "image_url": image_url,
            "detections": detections,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        return {"success": False, "reason": f"error: {exc}"}


def save_sample(frame_data: dict[str, Any], session_id: str) -> Path | None:
    """保存样本截图"""
    try:
        # 下载图片
        image_url = frame_data["image_url"]
        if image_url.startswith("/"):
            image_url = f"{API_BASE}{image_url}"

        img_resp = requests.get(image_url, timeout=10)
        img_resp.raise_for_status()

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        detections = frame_data.get("detections", [])

        if detections:
            # 有检测到时，按置信度命名
            best = max(detections, key=lambda x: x.get("confidence", 0))
            conf = best.get("confidence", 0)
            label = best.get("label", "unknown")
            filename = f"sample_{timestamp}_conf{int(conf*1000):03d}_{label}.jpg"
        else:
            # 未检测到，标记为待标注
            filename = f"sample_{timestamp}_no_detection.jpg"

        save_path = SAMPLES_DIR / filename
        save_path.write_bytes(img_resp.content)

        # 保存元数据
        meta_path = save_path.with_suffix(".json")
        meta_path.write_text(json.dumps(frame_data, indent=2, ensure_ascii=False), encoding="utf-8")

        return save_path
    except Exception:
        return None


def should_capture_dedup(last_capture_time: float | None) -> bool:
    """去重判断"""
    if last_capture_time is None:
        return True
    return time.time() - last_capture_time >= DEDUP_SECONDS


async def collect_samples(session_id: str | None, duration_seconds: int):
    """自动收集样本"""

    if session_id is None:
        session_id = get_session_id()
        print(f"自动获取 session_id: {session_id}")

    print(f"\n{'='*60}")
    print(f"开始收集翡翠样本")
    print(f"Session: {session_id}")
    print(f"时长: {duration_seconds} 秒 ({duration_seconds/60:.0f} 分钟)")
    print(f"截图间隔: {CAPTURE_INTERVAL} 秒")
    print(f"去重间隔: {DEDUP_SECONDS} 秒")
    print(f"保存目录: {SAMPLES_DIR}")
    print(f"{'='*60}\n")

    last_capture_time: float | None = None
    total_captured = 0
    total_with_detection = 0
    total_no_detection = 0

    end_time = time.time() + duration_seconds

    try:
        while time.time() < end_time:
            # 获取当前帧
            frame_data = capture_frame(session_id)

            if not frame_data["success"]:
                print(f"[跳过] {frame_data.get('reason')}")
                await asyncio.sleep(CAPTURE_INTERVAL)
                continue

            detections = frame_data.get("detections", [])

            # 去重判断
            if not should_capture_dedup(last_capture_time):
                await asyncio.sleep(CAPTURE_INTERVAL)
                continue

            # 保存样本
            save_path = save_sample(frame_data, session_id)
            if save_path:
                last_capture_time = time.time()
                total_captured += 1

                if detections:
                    best = max(detections, key=lambda x: x.get("confidence", 0))
                    conf = best.get("confidence", 0)
                    label = best.get("label", "unknown")
                    total_with_detection += 1
                    print(f"[{total_captured}] ✅ 检测到: {label} (conf={conf:.3f}) -> {save_path.name}")
                else:
                    total_no_detection += 1
                    print(f"[{total_captured}] ⚠️  未检测到 -> {save_path.name}")

            await asyncio.sleep(CAPTURE_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n用户中断")

    print(f"\n{'='*60}")
    print(f"收集完成!")
    print(f"总计截图: {total_captured} 张")
    print(f"  - 有检测到: {total_with_detection} 张")
    print(f"  - 未检测到: {total_no_detection} 张")
    print(f"保存目录: {SAMPLES_DIR}")
    print(f"{'='*60}")


# ============ 主入口 ============

def main():
    parser = argparse.ArgumentParser(description="自动收集翡翠直播间样本")
    parser.add_argument("--session-id", help="直播会话 ID（可选，自动获取）")
    parser.add_argument("--duration", type=int, default=7200, help="收集时长（秒），默认 7200=2小时")

    args = parser.parse_args()

    asyncio.run(collect_samples(args.session_id, args.duration))


if __name__ == "__main__":
    main()
