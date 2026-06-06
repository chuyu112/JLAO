# 0603 翡翠多模态识别交接

## 目标

做一个翡翠多模态识别能力，识别颜色、种水、样式、题材等属性，支持图片、VLM、OCR、STT、反馈学习融合。

当前路线是本地 Ollama 多模态模型优先，默认模型切到 `qwen3.5:9b`，保留 `qwen2.5vl:7b` 作为基线对比。

## 当前状态

默认 VLM 模型：

```text
qwen3.5:9b
```

默认 Ollama 地址：

```text
http://127.0.0.1:11434
```

先确保模型已安装：

```powershell
ollama pull qwen3.5:9b
```

项目脚本不需要先执行 `ollama run`。只要 Ollama 后台服务正常，脚本会通过 `/api/chat` 自动调用模型。

## 关键后端改动

### 默认 VLM 切到 qwen3.5:9b

文件：

- `backend/app/services/jade_vlm_service.py`

新增默认值：

```python
DEFAULT_OLLAMA_VLM_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_VLM_MODEL = "qwen3.5:9b"
```

`configured_vlm_http_url()` 和 `configured_vlm_http_model()` 现在默认走本机 Ollama 的 `qwen3.5:9b`。

### 修复 Ollama API 自动识别

原来 `auto` 模式只有 URL 以 `/api/chat` 结尾时才走 Ollama，默认 `http://127.0.0.1:11434` 可能误打 OpenAI 兼容接口 `/v1/chat/completions`。

已新增：

```python
def is_ollama_http_url(url: str) -> bool:
```

现在以下地址都会走 Ollama `/api/chat`：

- `http://127.0.0.1:11434`
- `http://localhost:11434`
- 以 `/api/chat` 结尾的地址

### VLM 状态字段

后端 VLM 状态现在会返回：

- `default_http_url`
- `default_http_model`
- `using_default_http_url`
- `using_default_http_model`

用于前端显示当前是默认模型还是环境变量配置模型。

## 颜色识别后处理

文件：

- `backend/app/services/jade_multimodal_service.py`

核心策略：

- OpenCV 颜色比例主要做诊断，不轻易覆盖 VLM 主判断。
- VLM 已经给出纯色时，OpenCV 不再把它改成 `飘花` 或 `多彩`。
- VLM 给粗花色如 `多彩` 时，OpenCV 可以辅助细化成 `春带彩`、`白底青`、`洒金`。
- 直播场景不要求颜色占全图 70%，应以翡翠主体 ROI 为主。

新增诊断字段：

- `opencv_pattern_candidate`
- `opencv_pattern_reason`
- `vlm_color_signal`
- `opencv_subject_colors`
- `opencv_frame_colors`
- `opencv_subject_roi`

## 行业术语调整

用户明确要求：

- 雕刻类统一叫 `挂件`。
- `牌子`、`龙牌`、`山水牌`、`无事牌` 不作为独立样式输出。
- `龙牌` 应输出 `style=挂件, theme=龙`。
- `山水牌` 应输出 `style=挂件, theme=山水`。
- `无事牌` 应输出 `style=挂件, theme=无事牌`。
- `吊坠` 只用于裸石坠、镶嵌坠、无明显雕刻题材的普通坠。

相关文件：

- `backend/app/services/jade_vlm_service.py`
- `backend/app/services/jade_multimodal_service.py`
- `backend/app/services/jade_feedback_learning_service.py`
- `backend/app/services/jade_training_service.py`

## 色彩层级

当前颜色输出和诊断按四层处理：

- `color`
- `color_family`
- `color_detail`
- `color_pattern`

规则：

- `洒金` 是花色结构，不是 `color_detail`。
- `洒金` 的 `color_family` 是 `黄色`。
- `白底青`、`飘花`、`春带彩`、`多彩`、`洒金` 属于 `color_pattern`。

## 测试脚本

### 单图测试

默认使用 `qwen3.5:9b`：

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_single_image_vlm.ps1 -Image path\to\image.png
```

指定旧模型：

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_single_image_vlm.ps1 -Image path\to\image.png -OllamaModel qwen2.5vl:7b
```

单图输出会打印：

- `model`
- `actual_vlm_model`
- `color/family/detail/pattern`
- `opencv_pattern_candidate`
- `vlm_color_signal`
- `subject_colors`
- `frame_colors`
- `subject_roi`

### 100 张颜色控制集

默认使用 `qwen3.5:9b`：

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_color_control_vlm.ps1 -ForceRename
```

如果模型没装，会提示：

```powershell
ollama pull qwen3.5:9b
```

### 双模型对比

默认对比顺序：

```text
qwen3.5:9b
qwen2.5vl:7b
```

命令：

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_model_compare.ps1 -ForceRename
```

主要输出：

- `tmp\jade-color-control-diagnosis-qwen3-5-9b.csv`
- `tmp\jade-color-control-diagnosis-qwen2-5vl-7b.csv`
- `tmp\jade-model-compare-summary.csv`
- `tmp\jade-model-compare-summary.json`
- `tmp\jade-model-compare-matrix.csv`
- `tmp\jade-review-queue.csv`

## 新增和修改的脚本

### 预测

文件：

- `scripts/predict_jade_manifest.py`

新增输出：

- `vlm_model`
- color layer 字段
- OpenCV 颜色诊断字段

### 评分

文件：

- `tmp/evaluate_jade_color_control_predictions.ps1`

新增保留：

- `predicted_vlm_model`
- `predicted_opencv_pattern_candidate`
- `predicted_opencv_pattern_reason`
- `predicted_vlm_color_signal`
- ROI 和颜色诊断 JSON

### 单模型汇总诊断

文件：

- `scripts/summarize_jade_color_control_run.py`

新增：

- `theme` 命中率
- `confusions` 错配对统计

### 模型对比总表

文件：

- `scripts/summarize_jade_model_compare.py`

用于生成：

- 每模型整体准确率
- 每维度最高频错配

### 逐样本矩阵

文件：

- `scripts/build_jade_model_compare_matrix.py`

用于生成：

- 每张图一行
- 每模型预测字段
- 每模型得分
- `best_model`
- `needs_review`

### 人工复看队列

文件：

- `scripts/build_jade_review_queue.py`

用于生成：

- `tmp\jade-review-queue.csv`

默认前 40 条最值得人工复看的样本。

### 模型对比入口

文件：

- `tmp/run_jade_model_compare.ps1`

现逻辑：

- 检查所有模型是否安装。
- 图片准备只做一次。
- 每模型只跑预测、评分、汇总。
- 最后生成 summary、matrix、review queue。

## 前端改动

### 识别实验室

文件：

- `frontend/src/pages/JadeRecognitionLab.vue`

新增：

- VLM 模型显示：`qwen3.5:9b（默认 Ollama）`
- 主体 ROI 色彩诊断
- 画面整体色彩诊断
- OpenCV 花色候选
- ROI 信息

### 商品库页面

文件：

- `frontend/src/pages/ProductLibrary.vue`

新增：

- VLM 卡片显示当前模型。
- 默认模型显示 `qwen3.5:9b（默认）`。
- 环境变量配置模型显示 `（配置）`。
- VLM 未启用时，提示当前模型和安装建议。

### 类型定义

文件：

- `frontend/src/types.ts`

新增 VLM 状态字段：

- `default_http_url`
- `default_http_model`
- `using_default_http_url`
- `using_default_http_model`

## 文档

文件：

- `docs/jade-live-recognition-runbook.md`

已追加：

- Qwen3.5 9B 默认路线
- `ollama run` 与脚本 API 调用区别
- 单图测试命令
- 100 张控制集命令
- 双模型对比命令
- 后端默认 VLM 说明

## 未验证

还没有跑过：

- 前端构建
- 后端测试
- 单图 qwen3.5 实测
- 100 张颜色控制集
- 双模型对比

因此不能标记目标完成。

## 下一步建议

先确认模型安装：

```powershell
ollama pull qwen3.5:9b
```

再跑单图验证：

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_single_image_vlm.ps1 -Image path\to\image.png
```

如果单图正常，再跑 100 张控制集：

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_color_control_vlm.ps1 -ForceRename
```

如果要判断新旧模型谁更适合翡翠任务，跑双模型对比：

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_model_compare.ps1 -ForceRename
```

优先看这些输出：

- `tmp\jade-model-compare-summary.csv`
- `tmp\jade-model-compare-matrix.csv`
- `tmp\jade-review-queue.csv`

## 当前风险

- `qwen3.5:9b` 是否已经安装未知。
- 前端 TypeScript 是否能通过构建未知。
- 后端默认 Ollama `/api/chat` 修复未实测。
- 颜色提示词和后处理理论上更稳，但还未跑真实图验证。
- 直播间颜色复杂，不能依赖全图平均色，仍需主体 ROI 和人工复核。

## 0603 追加

新增默认 VLM 环境检查脚本：

- `tmp/check_jade_default_vlm.ps1`

运行：

```powershell
powershell -ExecutionPolicy Bypass -File tmp\check_jade_default_vlm.ps1
```

作用：

- 检查 `python` 命令是否可用。
- 检查 Ollama 是否可访问。
- 检查默认模型 `qwen3.5:9b` 是否已安装。

该脚本不跑图片识别，只做环境准备检查。如果缺模型，会提示先运行：

```powershell
ollama pull qwen3.5:9b
```
