# JLAO Docker 部署指南

## 🐳 快速开始

### 前提条件

1. 安装 Docker Desktop (Windows)
   - 下载地址：https://www.docker.com/products/docker-desktop
   - 安装时勾选 "Use WSL 2 instead of Hyper-V"

2. 安装 NVIDIA Container Toolkit（GPU 支持）
   ```powershell
   # 在 PowerShell 中运行（管理员权限）
   # 1. 安装 Chocolatey
   Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
   
   # 2. 安装 NVIDIA Container Toolkit
   choco install nvidia-container-toolkit
   ```

3. 配置 Docker 使用 NVIDIA 运行时
   ```json
   // 编辑 C:\ProgramData\docker\config\daemon.json
   {
     "runtimes": {
       "nvidia": {
         "path": "nvidia-container-runtime",
         "runtimeArgs": []
       }
     }
   }
   ```

### 构建和启动

```bash
# 1. 进入项目目录
cd D:\JLAO

# 2. 构建 Docker 镜像
.\docker-run.bat build

# 3. 启动服务
.\docker-run.bat up

# 4. 查看日志
.\docker-run.bat logs

# 5. 停止服务
.\docker-run.bat down
```

### 常用命令

| 命令 | 说明 |
|---|---|
| `docker-run.bat build` | 构建 Docker 镜像 |
| `docker-run.bat up` | 启动服务 |
| `docker-run.bat down` | 停止服务 |
| `docker-run.bat logs` | 查看日志 |
| `docker-run.bat shell` | 进入容器 |
| `docker-run.bat clean` | 清理容器和镜像 |

## 📁 目录结构

```
JLAO/
├── Dockerfile              # Docker 镜像定义
├── docker-compose.yml      # Docker Compose 配置
├── docker-run.bat          # Windows 部署脚本
├── backend/                # 后端代码
│   ├── app/               # FastAPI 应用
│   └── requirements.txt   # Python 依赖
├── frontend/              # 前端代码
│   └── dist/             # 构建产物
└── deploy/                # 部署脚本
```

## 🔧 环境变量

在 `docker-compose.yml` 中配置：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `FUNASR_DEVICE` | `cuda` | FunASR 运行设备 |
| `PADDLEOCR_USE_GPU` | `true` | PaddleOCR 使用 GPU |
| `CUDA_VISIBLE_DEVICES` | `0` | 可见 GPU 设备 |

## 💾 数据持久化

Docker Compose 会自动创建以下卷：

| 卷名 | 用途 | 路径 |
|---|---|---|
| `jlao-models` | FunASR 模型缓存 | `~/.cache/modelscope` |
| `jlao-paddle` | PaddleOCR 模型缓存 | `~/.paddleocr` |

## 🚀 换电脑部署

1. 克隆代码仓库
2. 安装 Docker Desktop + NVIDIA Container Toolkit
3. 运行 `docker-run.bat build`
4. 运行 `docker-run.bat up`

## 🔍 故障排查

### 1. Docker 无法识别 GPU

```bash
# 检查 NVIDIA Docker 运行时
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi
```

### 2. 模型下载失败

```bash
# 进入容器手动下载模型
docker-run.bat shell
python -c "from funasr import AutoModel; AutoModel(model='paraformer-zh')"
```

### 3. 端口冲突

修改 `docker-compose.yml` 中的端口映射：
```yaml
ports:
  - "8002:8001"  # 改为 8002 端口
```

## 📚 参考文档

- [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- [Docker Compose](https://docs.docker.com/compose/)
