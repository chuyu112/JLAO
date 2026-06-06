# JLAO 本地开发环境 Docker 配置
# 使用 GPU 加速的 FunASR + PaddleOCR

FROM nvidia/cuda:12.8.0-cudnn-runtime-ubuntu22.04

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEBIAN_FRONTEND=noninteractive
ENV CUDA_VISIBLE_DEVICES=0

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-pip \
    python3.11-venv \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 设置 Python3.11 为默认
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# 升级 pip
RUN python -m pip install --upgrade pip setuptools wheel

# 创建工作目录
WORKDIR /app

# 复制 requirements
COPY backend/requirements.txt /app/requirements.txt

# 安装 Python 依赖（GPU 版本）
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128 \
    && pip install funasr paddlepaddle paddleocr \
    && pip install -r requirements.txt

# 复制应用代码
COPY backend/app /app/app
COPY backend/requirements.txt /app/requirements.txt

# 暴露端口
EXPOSE 8001

# 启动命令
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
