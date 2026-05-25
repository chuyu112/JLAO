import paramiko
import os

password = os.getenv("JLAO_SERVER_PASSWORD")
if not password:
    raise SystemExit("Set JLAO_SERVER_PASSWORD before running this script.")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('47.120.41.143', username='root', password=password, timeout=10)

commands = [
    ('检查 ossutil', 'which ossutil || which ossutil64 || echo "未安装"'),
    ('检查阿里云 CLI', 'which aliyun || echo "未安装"'),
    ('查找 OSS 相关配置', 'find / -name "*oss*" -o -name "*bucket*" 2>/dev/null | grep -v proc | head -20'),
    ('查找 jpasp 相关环境变量或配置', 'env | grep -i oss || true; env | grep -i jpasp || true'),
    ('检查是否有 OSS 挂载', 'df -h | grep -i oss || echo "无 OSS 挂载"'),
]

for title, cmd in commands:
    print(f'=== {title} ===')
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(out if out else (err if err else '无输出'))
    print()

client.close()
