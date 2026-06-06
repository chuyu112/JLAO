#!/usr/bin/env python3
"""
自动截图脚本：每 5-10 秒截图一次，自动去重
用法：python scripts/auto_screenshot.py --session-id xxx --interval 5 --duration 7200
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from PIL import Image

# ============ 配置 ============

# 截图保存目录
SCREENSHOTS_DIR = Path(__file__).resolve().parents[1] / "data" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# API 基础地址
API_BASE = "http://127.0.0.1:8000"

# 默认去重阈值（感知哈希差异小于此值视为重复）
DEDUP_THRESHOLD = 8


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
    """通过 API 截图"""
    try:
        # 获取最新帧
        resp = requests.get(f"{API_BASE}/api/sessions/{session_id}/frames", timeout=10)
        frames = resp.json()

        if not frames:
            return {"success": False, "reason": "no_frames"}

        # 取最新一帧
        latest = frames[0]
        image_url = latest.get("image_path", "")

        if not image_url:
            return {"success": False, "reason": "no_image_url"}

        # 下载图片
        if image_url.startswith("/"):
            image_url = f"{API_BASE}{image_url}"

        img_resp = requests.get(image_url, timeout=10)
        img_resp.raise_for_status()

        return {
            "success": True,
            "image_data": img_resp.content,
            "frame_id": latest.get("id", ""),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as exc:
        return {"success": False, "reason": f"error: {exc}"}


def perceptual_hash(image_data: bytes) -> str:
    """计算感知哈希（用于去重）"""
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_data))
        img = img.convert("L")  # 转灰度
        img = img.resize((8, 8), Image.Resampling.LANCZOS)  # 缩放到 8x8

        pixels = list(img.getdata())
        avg = sum(pixels) / len(pixels)

        # 生成哈希：大于平均值为1，否则为0
        bits = "".join("1" if p > avg else "0" for p in pixels)
        return hex(int(bits, 2))[2:].zfill(16)
    except Exception:
        return hashlib.md5(image_data).hexdigest()[:16]


def hamming_distance(hash1: str, hash2: str) -> int:
    """计算两个哈希的汉明距离"""
    try:
        x = int(hash1, 16) ^ int(hash2, 16)
        return bin(x).count("1")
    except Exception:
        return 999


def is_duplicate(image_data: bytes, existing_hashes: list[str]) -> tuple[bool, str]:
    """检查是否重复"""
    current_hash = perceptual_hash(image_data)

    for existing_hash in existing_hashes:
        distance = hamming_distance(current_hash, existing_hash)
        if distance <= DEDUP_THRESHOLD:
            return True, current_hash

    return False, current_hash


def save_screenshot(image_data: bytes, session_id: str, index: int) -> Path:
    """保存截图"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{session_id}_{timestamp}_{index:04d}.jpg"
    save_path = SCREENSHOTS_DIR / filename
    save_path.write_bytes(image_data)
    return save_path


async def auto_screenshot(
    session_id: str | None,
    interval_seconds: float,
    duration_seconds: int,
):
    """自动截图主循环"""

    if session_id is None:
        session_id = get_session_id()
        print(f"自动获取 session_id: {session_id}")

    print(f"\n{'='*60}")
    print(f"开始自动截图")
    print(f"Session: {session_id}")
    print(f"截图间隔: {interval_seconds} 秒")
    print(f"监控时长: {duration_seconds} 秒 ({duration_seconds/60:.0f} 分钟)")
    print(f"保存目录: {SCREENSHOTS_DIR}")
    print(f"{'='*60}\n")

    existing_hashes: list[str] = []
    total_captured = 0
    total_saved = 0
    total_duplicates = 0

    end_time = time.time() + duration_seconds
    index = 0

    try:
        while time.time() < end_time:
            index += 1

            # 截图
            result = capture_frame(session_id)

            if not result["success"]:
                print(f"[{index}] ❌ 截图失败: {result.get('reason')}")
                await asyncio.sleep(interval_seconds)
                continue

            image_data = result["image_data"]
            total_captured += 1

            # 去重检查
            is_dup, img_hash = is_duplicate(image_data, existing_hashes)

            if is_dup:
                total_duplicates += 1
                print(f"[{index}] ⏭️  重复截图，跳过 (已去重 {total_duplicates} 张)")
            else:
                # 保存
                save_path = save_screenshot(image_data, session_id, total_saved + 1)
                existing_hashes.append(img_hash)
                total_saved += 1

                # 限制哈希列表长度（内存优化）
                if len(existing_hashes) > 100:
                    existing_hashes = existing_hashes[-50:]

                print(f"[{index}] ✅ 保存: {save_path.name} (已保存 {total_saved} 张)")

            # 等待间隔
            elapsed = time.time() - (end_time - duration_seconds)
            remaining = interval_seconds - (elapsed % interval_seconds)
            await asyncio.sleep(max(0.1, remaining))

    except KeyboardInterrupt:
        print("\n\n用户中断")

    print(f"\n{'='*60}")
    print(f"截图完成!")
    print(f"总计尝试: {total_captured} 张")
    print(f"实际保存: {total_saved} 张")
    print(f"重复跳过: {total_duplicates} 张")
    print(f"保存目录: {SCREENSHOTS_DIR}")
    print(f"{'='*60}")


# ============ 主入口 ============

def main():
    parser = argparse.ArgumentParser(description="自动截图工具")
    parser.add_argument("--session-id", help="直播会话 ID（可选，自动获取）")
    parser.add_argument("--interval", type=float, default=5, help="截图间隔（秒），默认 5")
    parser.add_argument("--duration", type=int, default=7200, help="监控时长（秒），默认 7200=2小时")

    args = parser.parse_args()

    asyncio.run(auto_screenshot(args.session_id, args.interval, args.duration))


if __name__ == "__main__":
    main()
