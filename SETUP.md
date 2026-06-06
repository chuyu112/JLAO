# JLAO 换电脑部署指南

## 🚀 快速开始（新电脑）

### 1. 克隆代码仓库

```bash
git clone <你的仓库地址> D:\JLAO
cd D:\JLAO
```

### 2. 安装依赖

**方式 A：使用 Conda（推荐）**

```bash
# 1. 安装 Conda（如果未安装）
# 下载地址：https://docs.conda.io/en/latest/miniconda.html

# 2. 创建环境
conda create -n jlao python=3.11 -y

# 3. 激活环境
conda activate jlao

# 4. 安装 CUDA 依赖（如果有 GPU）
conda install cudatoolkit=12.8 -c nvidia

# 5. 安装 Python 依赖
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install funasr paddlepaddle-gpu==2.6.2 paddleocr==2.9.1
pip install -r backend/requirements.txt
```

**方式 B：使用虚拟环境**

```bash
# 1. 创建虚拟环境
python -m venv backend/.venv

# 2. 激活环境
backend/.venv/Scripts/activate

# 3. 安装依赖
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
pip install funasr paddlepaddle-gpu==2.6.2 paddleocr==2.9.1
pip install -r backend/requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 到 `.env`：

```bash
copy .env.example .env
```

编辑 `.env` 文件，配置你的 API 密钥。

### 4. 启动服务

```bash
# 激活环境
conda activate jlao

# 启动后端
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# 另开一个终端启动前端
cd frontend
npm install
npm run dev
```

## 📦 依赖清单

### 系统依赖

| 软件 | 版本 | 用途 |
|---|---|---|
| Python | 3.11+ | 运行环境 |
| CUDA | 12.8 | GPU 加速 |
| Node.js | 18+ | 前端构建 |
| PostgreSQL | 15+ | 数据库 |

### Python 依赖

| 包 | 版本 | 用途 |
|---|---|---|
| torch | 2.12.0+cu128 | PyTorch GPU |
| funasr | >=1.3.0 | 语音识别 |
| paddlepaddle-gpu | 2.6.2 | OCR 框架 |
| paddleocr | 2.9.1 | OCR 识别 |
| fastapi | 0.115.6 | Web 框架 |
| uvicorn | 0.34.0 | ASGI 服务器 |

## 💾 模型缓存

模型文件会自动下载到以下位置：

| 模型 | 路径 | 大小 |
|---|---|---|
| FunASR | `~/.cache/modelscope/` | ~1GB |
| PaddleOCR | `~/.paddleocr/` | ~100MB |

**换电脑时**：
- 可以复制这些缓存目录到新电脑
- 或者让程序自动重新下载

## 🔧 环境验证

### 检查 GPU

```bash
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
python -c "import torch; print(f'GPU: {torch.cuda.get_device_name(0)}')"
```

### 检查模型

```bash
python -c "from funasr import AutoModel; print('FunASR OK')"
python -c "from paddleocr import PaddleOCR; print('PaddleOCR OK')"
```

## 🐳 Docker 方案（可选）

如果你更喜欢 Docker，可以使用以下命令：

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## 📝 注意事项

1. **GPU 驱动**：确保安装最新的 NVIDIA 驱动
2. **CUDA 版本**：与 PyTorch 版本匹配
3. **模型下载**：首次启动会自动下载模型
4. **端口冲突**：确保 8001 和 3000 端口未被占用

## 🆘 常见问题

### 1. CUDA 版本不匹配

```bash
# 检查 CUDA 版本
nvidia-smi

# 安装对应版本的 PyTorch
# CUDA 12.8
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

### 2. 模型下载失败

```bash
# 手动下载模型
python -c "from funasr import AutoModel; AutoModel(model='paraformer-zh')"
```

### 3. 端口被占用

```bash
# 查找占用端口的进程
netstat -ano | findstr :8001

# 结束进程
taskkill /PID <PID> /F
```

## 📚 参考文档

- [PyTorch 安装指南](https://pytorch.org/get-started/locally/)
- [FunASR 文档](https://github.com/alibaba-damo-academy/FunASR)
- [PaddleOCR 文档](https://github.com/PaddlePaddle/PaddleOCR)
