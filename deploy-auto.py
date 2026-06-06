#!/usr/bin/env python3
"""JLAO 自动部署脚本 - 使用密码连接"""

import paramiko
import sys
import time
from pathlib import Path

# 服务器配置
SERVER_IP = "47.120.41.143"
SERVER_USER = "root"
SERVER_PASSWORD = "LEONkang@@"
LOCAL_PACKAGE = r"D:\JLAO\jlao-release.tar.gz"
REMOTE_PACKAGE = "/tmp/jlao-release.tar.gz"

def deploy():
    print("=" * 50)
    print("  JLAO 服务器部署")
    print("=" * 50)
    print()

    # 检查发布包
    package_path = Path(LOCAL_PACKAGE)
    if not package_path.exists():
        print(f"错误: 发布包不存在 {LOCAL_PACKAGE}")
        sys.exit(1)

    print(f"[JLAO] 发布包: {LOCAL_PACKAGE}")
    print(f"[JLAO] 服务器: {SERVER_IP}")
    print()

    # 创建 SSH 客户端
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        # 连接服务器
        print("[JLAO] 连接服务器...")
        ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASSWORD, timeout=30)
        print("[JLAO] 连接成功!")
        print()

        # 上传文件
        print("[JLAO] 上传发布包...")
        sftp = ssh.open_sftp()
        sftp.put(LOCAL_PACKAGE, REMOTE_PACKAGE)
        sftp.close()
        print("[JLAO] 上传完成!")
        print()

        # 执行安装脚本
        print("[JLAO] 在服务器上执行安装...")
        print("-" * 50)

        commands = [
            "rm -rf /tmp/jlao-release && mkdir -p /tmp/jlao-release",
            "tar -xzf /tmp/jlao-release.tar.gz -C /tmp/jlao-release",
            "bash /tmp/jlao-release/deploy/server-install.sh"
        ]

        for cmd in commands:
            print(f">>> {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()

            # 读取输出
            output = stdout.read().decode('utf-8', errors='ignore')
            error = stderr.read().decode('utf-8', errors='ignore')

            if output:
                print(output)
            if error:
                print(f"错误: {error}", file=sys.stderr)

            if exit_code != 0:
                print(f"命令失败，退出码: {exit_code}")
                break

        print("-" * 50)
        print()

    except paramiko.AuthenticationException:
        print("错误: 认证失败，请检查密码")
        sys.exit(1)
    except paramiko.SSHException as e:
        print(f"错误: SSH 连接失败 - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)
    finally:
        ssh.close()

    print("=" * 50)
    print("  部署完成!")
    print("=" * 50)
    print()
    print(f"访问地址: http://{SERVER_IP}")
    print()

if __name__ == "__main__":
    deploy()
