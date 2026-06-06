# 分布式采集配置

## 架构

```
┌─────────────────────────────────────────┐
│           服务器（47.120.41.143）        │
│  ┌─────────────┐    ┌───────────────┐  │
│  │   Nginx     │    │   PostgreSQL   │  │
│  │  （前端）    │    │  （数据库）     │  │
│  └─────────────┘    └───────────────┘  │
│  ┌─────────────┐    ┌───────────────┐  │
│  │  Redis      │    │   文件存储     │  │
│  │  任务队列    │    │  /uploads/    │  │
│  └─────────────┘    └───────────────┘  │
└─────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   ┌────────┐ ┌────────┐ ┌────────┐
   │ 电脑 A  │ │ 电脑 B │ │ 电脑 C │
   │采集直播间1│ │采集直播间2│ │采集直播间3│
   │本地GPU   │ │本地GPU   │ │本地GPU   │
   └────────┘ └────────┘ └────────┘
```

## 配置步骤

### 1. 服务器端配置

#### 安装 Redis

```bash
# 在服务器上安装 Redis
dnf install redis
systemctl enable redis
systemctl start redis
```

#### 配置防火墙

```bash
# 开放 Redis 端口
firewall-cmd --permanent --add-port=6379/tcp
firewall-cmd --reload
```

#### 配置 Redis 安全

```bash
# 编辑 /etc/redis/redis.conf
# 设置密码
requirepass your_redis_password

# 绑定地址
bind 0.0.0.0
```

### 2. 每台电脑配置

#### 环境变量

```bash
# .env 文件
JLAO_SERVER_URL=http://47.120.41.143:8001
JLAO_REDIS_URL=redis://:your_redis_password@47.120.41.143:6379/0
JLAO_WORKER_ID=worker-a  # 每台电脑不同
```

#### 启动后端

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### 注册工作节点

```bash
curl -X POST http://localhost:8000/api/workers/register \
  -H "Content-Type: application/json" \
  -d '{
    "worker_id": "worker-a",
    "capabilities": {
      "gpu": true,
      "gpu_model": "RTX 4090",
      "max_sessions": 2
    }
  }'
```

### 3. 任务分配

#### 创建采集任务

```bash
# 在任意电脑上创建任务
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "room_name": "浅玩翡翠-2号店",
    "config": {
      "platform": "视频号",
      "capture_interval": 5,
      "duration_hours": 2,
      "yolo_enabled": true,
      "record_enabled": true
    }
  }'
```

#### 工作节点自动获取任务

```bash
# 工作节点自动轮询获取任务
curl http://localhost:8000/api/workers/worker-a/tasks
```

### 4. 数据汇总

#### 截图汇总

所有截图自动上传到服务器：
- 路径：`/var/www/jlao/uploads/frames/{session_id}/`
- 数据库：PostgreSQL 记录元数据

#### 训练数据汇总

```bash
# 从服务器下载所有截图
rsync -avz root@47.120.41.143:/var/www/jlao/uploads/frames/ ./data/collect_frames/

# 合并训练集
python scripts/merge_training_data.py \
  --input ./data/collect_frames/ \
  --output ./data/jade_yolo/
```

## API 接口

### 工作节点管理

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/workers/register` | POST | 注册工作节点 |
| `/api/workers/{id}/heartbeat` | POST | 心跳检测 |
| `/api/workers/{id}/tasks` | GET | 获取任务列表 |

### 任务管理

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/tasks` | POST | 创建任务 |
| `/api/tasks/{id}/assign` | POST | 分配任务 |
| `/api/tasks/{id}/complete` | POST | 完成任务 |
| `/api/tasks` | GET | 获取所有任务 |

### 文件上传

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/sessions/{id}/frames/upload` | POST | 上传截图 |
| `/api/sessions/{id}/frames` | GET | 获取截图列表 |

## 监控

### 查看所有工作节点

```bash
curl http://localhost:8000/api/workers
```

### 查看所有任务

```bash
curl http://localhost:8000/api/tasks
```

### 查看任务统计

```bash
curl http://localhost:8000/api/tasks/stats
```

## 注意事项

1. **网络要求**：每台电脑需要能访问服务器（47.120.41.143）
2. **防火墙**：服务器需要开放 6379（Redis）、8001（后端 API）端口
3. **存储空间**：服务器需要有足够空间存储截图
4. **带宽**：上传截图会占用带宽，建议局域网或高速网络
