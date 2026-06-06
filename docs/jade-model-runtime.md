# 翡翠多模态模型运行时配置

系统现在有三层图像识别能力：

1. 轻量 OpenCV：默认启用，用于颜色、种水启发式和样式兜底。
2. YOLO 小模型：用于样式、题材、主体区域检测。
3. 本地 VLM：用于补充图片语义，重点提升观音、佛公、如意、山水等题材识别。

## 默认部署

默认部署只安装轻量依赖：

```bash
bash deploy/server-install.sh
```

默认不会安装 `ultralytics`、`torch`、`transformers`，避免服务器部署变慢或磁盘占用过大。

## 启用 YOLO

训练或推理 YOLO 需要：

```bash
export JLAO_INSTALL_YOLO=1
export JLAO_YOLO_MODEL=/opt/jlao/models/jade-yolo.pt
bash deploy/server-install.sh
```

模型文件位置可以是：

```text
models/jade-yolo.pt
backend/models/jade-yolo.pt
```

也可以通过 `JLAO_YOLO_MODEL` 指定绝对路径。

## 启用本地 VLM

本地视觉语言模型需要：

```bash
export JLAO_INSTALL_VLM=1
export JLAO_VLM_MODEL=/opt/models/Qwen2.5-VL-3B-Instruct
bash deploy/server-install.sh
```

如果服务器只用 CPU 或需要指定 PyTorch 源，可以加：

```bash
export JLAO_TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
```

VLM 适合补充：

- 题材：观音、佛公、如意、叶子、山水、貔貅、葫芦
- 样式：手镯、珠串、蛋面、吊坠、戒指、牌子、平安扣
- 颜色和种水：作为 OpenCV 与主播讲解之外的辅助判断

## 前端状态

商品库页面会显示：

- YOLO 是否启用
- VLM 是否启用
- 缺少模型还是缺少依赖
- 训练集和训练任务状态

如果未配置大模型，系统仍会使用：

```text
主播讲解文本 + OpenCV 颜色/种水/样式兜底
```

## 推荐阶段

前期：

```text
OpenCV + 主播讲解 + 人工校正反馈
```

中期：

```text
用反馈样本生成弱标注 -> 训练 jade-yolo.pt
```

后期：

```text
YOLO 精标模型 + 本地 VLM + 主播讲解融合
```
