#!/usr/bin/env python3
"""
自动上传前端到服务器
用法：python scripts/deploy_frontend.py
"""

import subprocess
import sys
from pathlib import Path

# 配置
LOCAL_DIR = Path("D:/JLAO/frontend/dist")
REMOTE_HOST = "root@47.120.41.143"
REMOTE_DIR = "/var/www/jlao"
PASSWORD = "LEONkang@@"  # 你的密码

def run_command(cmd: list[str], password: str = None) -> tuple[int, str, str]:
    """执行命令并返回结果"""
    try:
        # 使用 pexpect 或 subprocess
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = proc.communicate(input=password + "\n" if password else None)
        return proc.returncode, stdout, stderr
    except Exception as exc:
        return -1, "", str(exc)

def main():
    print("=" * 60)
    print("JLAO 前端部署")
    print("=" * 60)
    print()

    # 检查本地目录
    if not LOCAL_DIR.exists():
        print(f"错误: 本地目录不存在: {LOCAL_DIR}")
        sys.exit(1)

    print(f"本地目录: {LOCAL_DIR}")
    print(f"远程服务器: {REMOTE_HOST}")
    print(f"远程目录: {REMOTE_DIR}")
    print()

    # 使用 scp 上传
    print("[1/3] 上传文件到服务器...")
    cmd = [
        "scp",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "UserKnownHostsFile=/dev/null",
        "-r",
        f"{LOCAL_DIR}/.",
        f"{REMOTE_HOST}:{REMOTE_DIR}/",
    ]

    returncode, stdout, stderr = run_command(cmd, PASSWORD)

    if returncode != 0:
        print(f"错误: 上传失败")
        print(f"stdout: {stdout}")
        print(f"stderr: {stderr}")
        sys.exit(1)

    print("上传成功!")
    print()

    # 重启 nginx
    print("[2/3] 重启 nginx...")
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "UserKnownHostsFile=/dev/null",
        REMOTE_HOST,
        "nginx -t && systemctl restart nginx",
    ]

    returncode, stdout, stderr = run_command(cmd, PASSWORD)

    if returncode != 0:
        print(f"错误: nginx 重启失败")
        print(f"stdout: {stdout}")
        print(f"stderr: {stderr}")
        sys.exit(1)

    print("nginx 重启成功!")
    print()

    print("=" * 60)
    print("部署完成!")
    print("=" * 60)
    print(f"访问地址: https://jlao.szkakayiduo.com")

if __name__ == "__main__":
    main()
