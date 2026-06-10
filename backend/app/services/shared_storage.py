"""
共享文件存储服务 - 多台电脑上传截图到服务器
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


class SharedFileStorage:
    """共享文件存储"""

    def __init__(self, base_url: str = "http://127.0.0.1:8001"):
        self.base_url = base_url
        self.local_dir = Path("uploads/frames")
        self.local_dir.mkdir(parents=True, exist_ok=True)

    def upload_frame(
        self,
        session_id: str,
        image_data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """上传截图到服务器"""
        try:
            # 生成文件名
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            filename = f"frame_{session_id}_{timestamp}.jpg"

            # 上传到服务器
            files = {"file": (filename, image_data, "image/jpeg")}
            data = {"session_id": session_id, "metadata": json.dumps(metadata or {})}

            response = requests.post(
                f"{self.base_url}/api/sessions/{session_id}/frames/upload",
                files=files,
                data=data,
                timeout=30,
            )
            response.raise_for_status()

            return {
                "success": True,
                "filename": filename,
                "url": response.json().get("image_path", ""),
                "metadata": metadata,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def download_frame(self, url: str, local_path: Path) -> bool:
        """从服务器下载截图"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            local_path.write_bytes(response.content)
            return True
        except Exception:
            return False

    def sync_frames(self, session_id: str) -> list[dict[str, Any]]:
        """同步服务器的截图列表"""
        try:
            response = requests.get(
                f"{self.base_url}/api/sessions/{session_id}/frames",
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return []


class LocalFrameBuffer:
    """本地帧缓冲 - 批量上传"""

    def __init__(self, max_size: int = 100):
        self.buffer: list[dict[str, Any]] = []
        self.max_size = max_size
        self.storage = SharedFileStorage()

    def add_frame(self, session_id: str, image_data: bytes, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """添加帧到缓冲"""
        self.buffer.append({
            "session_id": session_id,
            "image_data": image_data,
            "metadata": metadata or {},
            "timestamp": time.time(),
        })

        # 如果缓冲满了，批量上传
        if len(self.buffer) >= self.max_size:
            return self.flush()

        return {"success": True, "buffered": True, "count": len(self.buffer)}

    def flush(self) -> dict[str, Any]:
        """批量上传缓冲的帧"""
        results = []
        for item in self.buffer:
            result = self.storage.upload_frame(
                item["session_id"],
                item["image_data"],
                item["metadata"],
            )
            results.append(result)

        self.buffer.clear()
        return {"success": True, "uploaded": len(results), "results": results}

    def __del__(self):
        """析构时上传剩余帧"""
        if self.buffer:
            self.flush()
