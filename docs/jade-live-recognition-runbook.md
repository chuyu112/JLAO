# 翡翠直播多模态识别运行流程

## 当前目标

用本地 Ollama/Qwen2.5VL + 后端融合逻辑识别直播间翡翠图片的：

- 颜色
- 种水
- 样式
- 题材

识别主字段保持简单：`color / water / style / theme`。

诊断字段用于解释复杂直播画面：`color_family / color_detail / color_pattern / 主体 ROI 颜色候选 / 画面整体颜色候选`。

## YOLO 实时识别准则

这两条准则优先级高于阈值调参、低分候选展示和自动入库策略。YOLO 每帧结果先视为内部候选，只有满足稳定性和追踪约束后，才能升级为前端确认框或业务判断。

### 1. 高精度优先：宁可漏识别，不可错判断

- 默认状态应是“未确认识别”，不是“低分猜测”。
- 低置信度 YOLO 结果只能作为内部候选，不能直接写入商品判断、成交卡片、复盘或训练样本。
- 当候选受到手、弹幕、商品卡、背景货品、界面浮层干扰时，必须丢弃或保持未确认。
- 系统只有在多帧稳定、位置合理、置信度和上下文足够时，才允许升级为“确认识别”。
- 不确定时保持当前状态或返回未识别，不能为了有结果而硬猜。

### 2. 同货追踪优先：框跟货走，不许乱跳

- 主播通常会围绕同一件货讲解至少约 1 分钟，长时可达 10 分钟；系统应假设当前货有持续性。
- YOLO 每帧检测只产生候选框；正式显示和业务判断必须基于同一 `track_id` 的稳定轨迹。
- 当前货被主播摆动、旋转、遮挡或短暂移出画面时，框应平滑跟随或短暂保持 lost 状态，不能跳到其它候选。
- 切换货品必须有明确证据，例如旧 track 连续丢失、新候选连续稳定、画面/商品卡/话术共同支持换货。
- 在跟踪状态下允许更新框的位置，不允许频繁更新商品身份。

## 模型环境

Ollama 本地服务：

```powershell
ollama serve
```

已使用的模型名：

```powershell
qwen2.5vl:7b
```

后端批量脚本会设置：

```powershell
$env:JLAO_VLM_HTTP_URL='http://127.0.0.1:11434'
$env:JLAO_VLM_HTTP_MODEL='qwen2.5vl:7b'
$env:JLAO_VLM_HTTP_FORMAT='ollama'
$env:JLAO_VLM_HTTP_TIMEOUT='180'
$env:JLAO_JADE_OPENCV_FILL='color-water'
```

## 两套测试集

`颜色控制集`

用途：测模型在颜色明确、主体干净时的识别上限。

提示词文件：

```text
tmp/jade-color-control-prompts-v1.csv
tmp/jade-color-control-prompts-v1.txt
```

图片目录：

```text
tmp/jade-color-control-inbox
```

运行：

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_color_control_vlm.ps1 -ForceRename
```

`直播压力集`

用途：测直播间复杂背景、局部颜色、手托、托盘、补光、屏幕色偏下的真实鲁棒性。

提示词文件：

```text
tmp/jade-live-color-stress-prompts-v1.csv
tmp/jade-live-color-stress-prompts-v1.txt
```

图片目录：

```text
tmp/jade-live-color-stress-inbox
```

运行：

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_live_color_stress_vlm.ps1 -ForceRename
```

## 图片命名规则

生成图片按编号保存：

```text
1.png
2.png
...
100.png
```

脚本会按提示词 CSV 自动复制并重命名到标准图片目录。

## 单图快速调试

用于先拿一张直播截图看主识别结果和颜色诊断，不必等 100 张测试集。

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_single_image_vlm.ps1 -Image path\to\image.png
```

可选附加主播讲解文本：

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_single_image_vlm.ps1 -Image path\to\image.png -Text "糯冰阳绿如意挂件"
```

输出：

```text
tmp/jade-single-image-manifest.csv
tmp/jade-single-image-prediction.csv
```

## 输出文件

颜色控制集输出：

```text
tmp/jade-color-control-images
tmp/jade-color-control-manifest.csv
tmp/jade-color-control-quality.csv
tmp/jade-color-control-predictions.csv
tmp/jade-color-control-score.csv
tmp/jade-color-control-diagnosis.json
tmp/jade-color-control-diagnosis.csv
```

直播压力集输出：

```text
tmp/jade-live-color-stress-images
tmp/jade-live-color-stress-manifest.csv
tmp/jade-live-color-stress-quality.csv
tmp/jade-live-color-stress-predictions.csv
tmp/jade-live-color-stress-score.csv
tmp/jade-live-color-stress-diagnosis.json
tmp/jade-live-color-stress-diagnosis.csv
```

## 重点看哪些指标

颜色主分类：

```text
predicted_color
```

颜色分层：

```text
predicted_color_family
predicted_color_detail
predicted_color_pattern
```

直播背景干扰诊断：

```text
predicted_subject_colors_json
predicted_frame_colors_json
predicted_subject_roi_json
```

准确率：

```text
tmp/*-score.csv
tmp/*-diagnosis.json
```

失败归因：

```text
failure_bucket
quality_flags
```

## 失败桶含义

`generation_quality_issue`

图本身颜色弱、过曝、偏灰、目标色不可见。

`model_color_family_miss`

模型连大色系都看错。

`fine_color_detail_miss`

大色系对了，但细分色错，例如阳绿/辣绿/苹果绿混淆。

`color_pattern_miss`

花色结构错，例如白底青/飘花/春带彩/洒金混淆。

`canonical_color_merge_issue`

分层信息基本对，但最终 `color` 合成规则错。

`all_color_layers_ok`

颜色分层全对。

## 标签口径

样式：

```text
挂件
```

用于雕刻类，包括观音、佛公、叶子、如意、葫芦、福瓜、貔貅、龙牌、山水牌、无事牌。

题材：

```text
观音 / 佛公 / 如意 / 叶子 / 山水 / 貔貅 / 葫芦 / 无事牌 / 财神 / 龙 / 福瓜
```

`吊坠` 只用于无明显雕刻题材的镶嵌坠、裸石坠或普通坠类。

颜色结构：

```text
纯色 / 飘花 / 白底青 / 春带彩 / 多彩 / 洒金
```

`洒金` 是花色结构，不是细分色。

## 前端查看位置

实验室页面：

```text
翡翠多模态识别
```

每张识别卡片会显示：

- 主识别字段
- 色系/细分/花色
- 主体 ROI 颜色候选
- 画面整体颜色候选
- ROI 面积和尺寸

直播源面板：

```text
颜色诊断
```

显示实时帧的颜色分层、主体 ROI 颜色候选和画面整体颜色候选。

## 历史反馈清理

默认生成新文件，不覆盖原始反馈：

```powershell
python scripts\normalize_jade_feedback_taxonomy.py --pretty
```

输出：

```text
data/jade_feedback.normalized.jsonl
```

确认后才覆盖原反馈：

```powershell
python scripts\normalize_jade_feedback_taxonomy.py --in-place --pretty
```

## VLM 模型路线和对比测试

当前推荐把模型选择当成可替换组件，不把识别链路绑死在某一个模型上。

### 现阶段优先级

1. `qwen2.5vl:7b`
   - 现有基线模型。
   - 用来保留历史对比，不建议继续作为唯一目标。

2. `qwen3.5:9b`
   - 当前优先试跑模型。
   - 适合 5070Ti / 未来 3090 的本地图片理解、OCR、直播截图识别。
   - 重点看同一批翡翠图上的颜色、种水、样式、题材命中率，而不是只看通用榜单。

3. `qwen3.6:27b` / `qwen3.6:35b`
   - 3090 到位后再试。
   - `35b` 对 24GB 显存更紧，先用 `27b` 做稳定性验证更现实。

4. `qwen3.7-max`
   - 只作为云端 Agent / 复杂任务总控候选。
   - 不作为本地直播逐帧翡翠识别主模型。

### 拉取 qwen3.5:9b

```powershell
ollama pull qwen3.5:9b
```

### 单图指定模型测试

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_single_image_vlm.ps1 -Image path\to\image.png -OllamaModel qwen3.5:9b
```

输出里重点看：

- `color/family/detail/pattern`
- `opencv_pattern_candidate`
- `vlm_color_signal`
- `subject_colors`
- `frame_colors`
- `subject_roi`

### 100 张颜色控制集双模型对比

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_model_compare.ps1 -ForceRename
```

默认对比：

- `qwen2.5vl:7b`
- `qwen3.5:9b`

主要输出：

- `tmp\jade-color-control-diagnosis-qwen2-5vl-7b.csv`
- `tmp\jade-color-control-diagnosis-qwen3-5-9b.csv`

判断模型是否更好，优先看这些指标：

- `color_family` 命中率：先看大色系是否稳定。
- `color_detail` 命中率：再看阳绿、辣绿、苹果绿、晴水、蓝水等细分色。
- `color_pattern` 命中率：看飘花、白底青、春带彩、洒金是否被识别成正确结构。
- `water` 命中率：种水是弱项，要结合人工抽检。
- `predicted_vlm_color_signal`：如果为 `true`，OpenCV 默认只作诊断，不应覆盖 VLM 主色。
- `predicted_opencv_pattern_candidate`：用于定位后处理候选，不等于最终颜色。

### 直播压力集指定模型测试

```powershell
powershell -ExecutionPolicy Bypass -File tmp\run_jade_live_color_stress_vlm.ps1 -ForceRename -OllamaModel qwen3.5:9b
```

直播压力集不要要求颜色占整张图 70%。真实直播场景里手、托盘、背景、灯光都会干扰，判断标准应以主体 ROI 和 VLM 主判断为准。

### 当前默认模型

测试入口默认模型已经切到 `qwen3.5:9b`。

不传 `-OllamaModel` 时，这些脚本默认使用 `qwen3.5:9b`：

- `tmp\run_jade_single_image_vlm.ps1`
- `tmp\run_jade_color_control_vlm.ps1`
- `tmp\run_jade_live_color_stress_vlm.ps1`

`qwen2.5vl:7b` 只保留为基线模型，用于 `tmp\run_jade_model_compare.ps1` 对比。

如果本机还没安装默认模型，先执行：

```powershell
ollama pull qwen3.5:9b
```

### `ollama run` 和项目脚本的区别

手动确认模型能启动时，可以运行：

```powershell
ollama run qwen3.5:9b
```

这会进入 Ollama 的交互聊天界面，退出输入：

```text
/bye
```

项目批量识别脚本不需要先进入 `ollama run`。只要模型已经通过 `ollama pull qwen3.5:9b` 下载完成，并且 Ollama 服务在后台运行，脚本会通过 `http://127.0.0.1:11434/api/chat` 调用模型。

### 后端默认 VLM

后端服务层默认也已经切到本机 Ollama：

- `JLAO_VLM_HTTP_URL` 默认：`http://127.0.0.1:11434`
- `JLAO_VLM_HTTP_MODEL` 默认：`qwen3.5:9b`

也就是说，不额外设置环境变量时，后端会优先尝试调用 `qwen3.5:9b`。如果要临时回到旧基线，可以在启动后端前设置：

```powershell
$env:JLAO_VLM_HTTP_MODEL = "qwen2.5vl:7b"
```

如果要指定别的模型，例如 3090 后测试更大模型：

```powershell
$env:JLAO_VLM_HTTP_MODEL = "qwen3.6:27b"
```

### 默认 VLM 准备检查

只检查本机环境，不跑图片识别：

```powershell
powershell -ExecutionPolicy Bypass -File tmp\check_jade_default_vlm.ps1
```

检查项：

- `python` 命令是否可用
- Ollama 是否可访问
- `qwen3.5:9b` 是否已安装

如果模型缺失，先执行：

```powershell
ollama pull qwen3.5:9b
```
