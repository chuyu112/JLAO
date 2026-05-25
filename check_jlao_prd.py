import paramiko
import os

password = os.getenv("JLAO_SERVER_PASSWORD")
if not password:
    raise SystemExit("Set JLAO_SERVER_PASSWORD before running this script.")

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('47.120.41.143', username='root', password=password, timeout=10)

commands = [
    ('jlao 根目录', 'ls -la /opt/jlao/'),
    ('查找 PRD/文档', 'find /opt/jlao -maxdepth 3 -type f \( -iname "*.md" -o -iname "*prd*" -o -iname "*spec*" -o -iname "*plan*" -o -iname "*需求*" -o -iname "*mvp*" \) 2>/dev/null | grep -v __pycache__ | head -20'),
    ('backend 结构', 'find /opt/jlao/backend -maxdepth 3 -type f | grep -v __pycache__ | grep -v .venv | head -30'),
    ('main.py 内容', 'cat /opt/jlao/backend/app/main.py'),
    ('schemas.py 内容', 'cat /opt/jlao/backend/app/schemas.py'),
    ('state.py 内容', 'cat /opt/jlao/backend/app/state.py'),
    ('前端目录', 'ls -la /var/www/jlao/ | head -20'),
]

for title, cmd in commands:
    print(f'=== {title} ===')
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(out if out else (err if err else '无输出'))
    print()

client.close()
