# JLAO 项目今日工作总结

> **日期**：2026-06-06
> **工作人员**：Worker A（第一台电脑）
> **服务器**：47.120.41.143

---

## 一、今日完成工作

### 1. 前端界面优化

| 修改项 | 状态 | 说明 |
|---|---|---|
| ✅ **按钮样式** | 完成 | 绿色渐变 + 凸起阴影 + 悬停动画 |
| ✅ **"接入视频流"按钮** | 完成 | 明显、凸起、立体效果 |
| ✅ **录屏按钮** | 完成 | 橙色 → 红色脉冲（录制时） |
| ✅ **停止按钮** | 完成 | 灰色 → 悬停变红 |
| ✅ **店名和按钮重叠** | 修复 | `flex-wrap: wrap` |
| ✅ **YOLO 视频流尺寸** | 放大 | `height: min(900px, ...)` |
| ✅ **客户线索** | 添加 | 显示真实弹幕用户名字 |
| ✅ **设置按钮** | 添加 | 顶部导航栏 |
| ✅ **删除 scrcpy 驱动面板** | 完成 | 移到设置里 |

### 2. 功能开发

| 功能 | 状态 | 说明 |
|---|---|---|
| ✅ **录屏功能** | 完成 | WebM/MP4 格式，自动下载 |
| ✅ **截屏功能** | 完成 | `takeScreenshot()` |
| ✅ **自动识别直播间名称** | 恢复 | 去掉固定名称，自动识别 |
| ✅ **scrcpy 最小化修复** | 完成 | `setTimeout` 替代 `requestAnimationFrame` |

### 3. 分布式架构

| 文件 | 说明 |
|---|---|
| `DISTRIBUTED.md` | 分布式多机协同采集架构文档 |
| `backend/app/services/distributed_scheduler.py` | Redis 任务调度器 |
| `backend/app/services/shared_storage.py` | 共享文件存储 |

### 4. GitHub 仓库清理

| 操作 | 结果 |
|---|---|
| ✅ 清理大文件 | `git filter-repo` |
| ✅ 更新 `.gitignore` | 忽略训练数据、模型文件 |
| ✅ 重新推送 | 仓库从 894 MB → **301 KB** |

---

## 二、服务器配置

### Redis 安装

```bash
# 已安装并运行
dnf install redis -y
systemctl enable redis
systemctl start redis
redis-cli ping  # 返回 PONG
```

### 防火墙

```bash
# 已开放端口
firewall-cmd --permanent --add-port=6379/tcp  # Redis
firewall-cmd --permanent --add-port=8001/tcp  # 后端 API
```

---

## 三、本地后端

### 启动命令

```powershell
cd D:\JLAO\backend
.venv-local\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

### 访问地址

| 服务 | 地址 |
|---|---|
| 前端 | `https://jlao.szkakayiduo.com` |
| 本地后端 | `http://127.0.0.1:8002` |
| 服务器后端 | `http://47.120.41.143:8001` |
| Redis | `redis://47.120.41.143:6379` |

---

## 四、明日工作计划

### 1. 测试分布式采集

| 任务 | 说明 |
|---|---|
| 注册 Worker A | `POST /api/workers/register` |
| 创建采集任务 | `POST /api/tasks` |
| 开始采集 | 接入视频流 + 录屏 |
| 验证数据上传 | 检查服务器 `/uploads/` |

### 2. 多机协同

| 任务 | 说明 |
|---|---|
| 配置 Worker B | 第二台电脑 |
| 配置 Worker C | 第三台电脑 |
| 任务分配测试 | Redis 队列 |
| 数据汇总验证 | 截图合并 |

### 3. YOLO 训练

| 任务 | 说明 |
|---|---|
| 收集样本 | 2 小时监控截图 |
| 筛选低置信度 | 1%-30% |
| 人工标注 | LabelImg |
| 图生图增强 | OpenAI Image-2 |
| 增量训练 | `train_jade_yolo.py` |

---

## 五、关键文件位置

### 本地

| 文件/目录 | 路径 |
|---|---|
| 项目根目录 | `D:\JLAO\` |
| 前端代码 | `D:\JLAO\frontend\` |
| 后端代码 | `D:\JLAO\backend\` |
| 虚拟环境 | `D:\JLAO\backend\.venv-local\` |
| 截图保存 | `D:\JLAO\uploads\frames\` |
| 训练数据 | `D:\JLAO\data\jade_yolo\` |
| 模型文件 | `D:\JLAO\models\jade-yolo.pt` |

### 服务器

| 文件/目录 | 路径 |
|---|---|
| 前端部署 | `/var/www/jlao/` |
| 后端 API | `http://47.120.41.143:8001` |
| 数据库 | PostgreSQL |
| Redis | `47.120.41.143:6379` |
| 截图存储 | `/var/www/jlao/uploads/frames/` |

---

## 六、部署命令

### 构建前端

```powershell
cd D:\JLAO\frontend
npm run build
```

### 上传到服务器

```powershell
cd D:\JLAO
scp -r frontend/dist/* root@47.120.41.143:/var/www/jlao/
```

### 重启 nginx

```powershell
ssh root@47.120.41.143 "nginx -t && systemctl restart nginx"
```

---

## 七、GitHub 仓库

| 项目 | 地址 |
|---|---|
| 仓库地址 | `https://github.com/chuyu112/JLAO` |
| SSH 地址 | `git@github.com:chuyu112/JLAO.git` |
| 当前大小 | **301 KB** |

---

## 八、联系方式

| 项目 | 信息 |
|---|---|
| 服务器 IP | `47.120.41.143` |
| 域名 | `jlao.szkakayiduo.com` |
| 部署文档 | `D:\JLAO\DEPLOY.md` |
| 分布式文档 | `D:\JLAO\DISTRIBUTED.md` |

---

## 九、备注

1. **Redis 已安装** — 服务器上运行正常
2. **大文件已清理** — GitHub 仓库只有 301 KB
3. **自动识别已恢复** — 不再固定直播间名称
4. **分布式架构已设计** — 等待多机测试
5. **YOLO 训练待进行** — 需要收集样本

---

**明日继续！**
