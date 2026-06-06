"""
分布式任务调度器 - 协调多台电脑采集多个直播间
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import redis


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CaptureTask:
    """采集任务"""
    task_id: str
    session_id: str
    room_name: str
    worker_id: str | None  # 分配给哪台电脑
    status: TaskStatus
    created_at: str
    started_at: str | None
    completed_at: str | None
    config: dict[str, Any]  # 采集配置


class DistributedScheduler:
    """分布式任务调度器"""

    def __init__(self, redis_url: str = "redis://47.120.41.143:6379/0"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.task_prefix = "jlao:task:"
        self.worker_prefix = "jlao:worker:"
        self.lock_prefix = "jlao:lock:"

    def register_worker(self, worker_id: str, capabilities: dict[str, Any]) -> bool:
        """注册工作节点"""
        key = f"{self.worker_prefix}{worker_id}"
        data = {
            "worker_id": worker_id,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "last_heartbeat": time.time(),
            "capabilities": json.dumps(capabilities),
            "status": "idle",
        }
        self.redis.hset(key, mapping=data)
        self.redis.expire(key, 300)  # 5分钟过期
        return True

    def heartbeat(self, worker_id: str) -> bool:
        """心跳检测"""
        key = f"{self.worker_prefix}{worker_id}"
        if not self.redis.exists(key):
            return False
        self.redis.hset(key, "last_heartbeat", str(time.time()))
        self.redis.expire(key, 300)
        return True

    def create_task(self, room_name: str, config: dict[str, Any]) -> CaptureTask:
        """创建采集任务"""
        task_id = f"task-{int(time.time() * 1000)}"
        task = CaptureTask(
            task_id=task_id,
            session_id=f"live-{task_id}",
            room_name=room_name,
            worker_id=None,
            status=TaskStatus.PENDING,
            created_at=datetime.now(timezone.utc).isoformat(),
            started_at=None,
            completed_at=None,
            config=config,
        )

        key = f"{self.task_prefix}{task_id}"
        self.redis.hset(key, mapping={
            "task_id": task_id,
            "session_id": task.session_id,
            "room_name": room_name,
            "worker_id": "",
            "status": task.status.value,
            "created_at": task.created_at,
            "config": json.dumps(config),
        })

        # 加入待分配队列
        self.redis.lpush("jlao:tasks:pending", task_id)

        return task

    def assign_task(self, worker_id: str) -> CaptureTask | None:
        """为工作节点分配任务"""
        # 检查是否有待分配任务
        task_id = self.redis.rpop("jlao:tasks:pending")
        if not task_id:
            return None

        # 获取锁
        lock_key = f"{self.lock_prefix}{task_id}"
        if not self.redis.set(lock_key, worker_id, nx=True, ex=30):
            return None

        # 分配任务
        key = f"{self.task_prefix}{task_id}"
        self.redis.hset(key, mapping={
            "worker_id": worker_id,
            "status": TaskStatus.RUNNING.value,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })

        # 更新工作节点状态
        worker_key = f"{self.worker_prefix}{worker_id}"
        self.redis.hset(worker_key, "status", "running")

        return self._get_task(task_id)

    def complete_task(self, task_id: str, worker_id: str, result: dict[str, Any]) -> bool:
        """完成任务"""
        key = f"{self.task_prefix}{task_id}"

        # 验证任务归属
        current_worker = self.redis.hget(key, "worker_id")
        if current_worker != worker_id:
            return False

        self.redis.hset(key, mapping={
            "status": TaskStatus.COMPLETED.value,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result": json.dumps(result),
        })

        # 更新工作节点状态
        worker_key = f"{self.worker_prefix}{worker_id}"
        self.redis.hset(worker_key, "status", "idle")

        return True

    def get_worker_tasks(self, worker_id: str) -> list[CaptureTask]:
        """获取工作节点的任务列表"""
        tasks = []
        for key in self.redis.scan_iter(match=f"{self.task_prefix}*"):
            task = self._get_task_from_key(key)
            if task and task.worker_id == worker_id:
                tasks.append(task)
        return tasks

    def get_all_tasks(self) -> list[CaptureTask]:
        """获取所有任务"""
        tasks = []
        for key in self.redis.scan_iter(match=f"{self.task_prefix}*"):
            task = self._get_task_from_key(key)
            if task:
                tasks.append(task)
        return tasks

    def _get_task(self, task_id: str) -> CaptureTask | None:
        """获取任务"""
        key = f"{self.task_prefix}{task_id}"
        return self._get_task_from_key(key)

    def _get_task_from_key(self, key: str) -> CaptureTask | None:
        """从 key 获取任务"""
        data = self.redis.hgetall(key)
        if not data:
            return None

        return CaptureTask(
            task_id=data.get("task_id", ""),
            session_id=data.get("session_id", ""),
            room_name=data.get("room_name", ""),
            worker_id=data.get("worker_id") or None,
            status=TaskStatus(data.get("status", "pending")),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at") or None,
            completed_at=data.get("completed_at") or None,
            config=json.loads(data.get("config", "{}")),
        )

    def release_stale_tasks(self, max_idle_seconds: int = 60) -> int:
        """释放超时任务"""
        released = 0
        now = time.time()

        for key in self.redis.scan_iter(match=f"{self.worker_prefix}*"):
            data = self.redis.hgetall(key)
            if not data:
                continue

            last_heartbeat = float(data.get("last_heartbeat", 0))
            if now - last_heartbeat > max_idle_seconds:
                worker_id = data.get("worker_id", "")
                # 释放该工作节点的任务
                for task_key in self.redis.scan_iter(match=f"{self.task_prefix}*"):
                    task_data = self.redis.hgetall(task_key)
                    if task_data.get("worker_id") == worker_id and task_data.get("status") == "running":
                        self.redis.hset(task_key, "status", "pending")
                        self.redis.hset(task_key, "worker_id", "")
                        self.redis.lpush("jlao:tasks:pending", task_data.get("task_id", ""))
                        released += 1

                # 删除工作节点
                self.redis.delete(key)

        return released
