# 翡翠多模态识别训练流程

目标：用图片、主播文本、人工标签和 YOLO 训练数据，提升翡翠 `颜色 / 种水 / 样式 / 题材` 识别。

## 快捷命令

推荐使用统一入口，默认使用本项目虚拟环境 Python：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 status -Pretty
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 static
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 check -Manifest D:\jade\samples.csv -Pretty
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 plan -Manifest D:\jade\samples.csv -Pretty
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 class-reference -Output data\jade_yolo_class_reference.csv
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 analyze -Image D:\jade\images\sample.jpg -Text "冰种阳绿观音吊坠" -Output data\jade_single_prediction.json -Pretty
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 dry-run-import -Manifest D:\jade\samples.csv
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 import -Manifest D:\jade\samples.csv
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 export-feedback -Output data\jade_feedback_manifest.csv
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 train -Manifest D:\jade\samples.csv -RunStaticCheck -IncludeRows -ExportMistakes -PackageArtifacts
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 predict-manifest -Manifest D:\jade\samples.csv -Output data\jade_manifest_predictions.csv -Pretty
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 export-mistakes -Output data\jade_eval_mistakes.csv
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 review-manifest -Output data\jade_review_manifest.csv
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 merge-manifests -Manifest D:\jade\samples.csv -SecondaryManifest data\jade_review_manifest.csv -Output D:\jade\samples_merged.csv
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 package -Output models\jade-yolo-artifacts.zip
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 check-package -Output models\jade-yolo-artifacts.zip -Pretty
```

## 1. 准备样本清单

复制模板：

```powershell
Copy-Item data\jade_sample_manifest_template.csv D:\jade\samples.csv
```

也可以从图片目录生成待复核 manifest：

```powershell
python scripts/create_jade_manifest_from_images.py --image-dir D:\jade\images --output D:\jade\samples.csv --recursive --whole-image-box
```

脚本会从文件名和文件夹名弱推断 `color/water/style/theme/class_name`，生成后必须人工检查，再进入后续检查和训练流程。

填写真实图片路径和人工标签。字段：

```csv
image,color,water,style,theme,text,class_name,x_center,y_center,width,height
```

字段含义：

- `image`：本地图片路径，必填。
- `color`：颜色，如 `阳绿`、`蓝水`、`晴水`、`紫罗兰`、`白冰`、`飘花`、`黄翡`、`墨翠`、`红翡`。
- `water`：种水，如 `玻璃种`、`高冰`、`冰种`、`冰糯`、`糯冰`、`细糯`、`糯种`、`豆种`。
- `style`：样式，如 `手镯`、`珠串`、`蛋面`、`吊坠`、`戒指`、`牌子`、`平安扣`、`摆件`。
- `theme`：题材，如 `观音`、`佛公`、`如意`、`叶子`、`山水`、`貔貅`、`葫芦`、`无事牌`、`财神`、`龙牌`。
- `text`：主播讲解文本，可选，但建议填写。
- `class_name`：YOLO 类，可选；系统可以从 `style/theme` 推断。
- `x_center,y_center,width,height`：YOLO 归一化框，可选；单主体图片可用整图框 `0.5,0.5,0.85,0.85`。
- 如果一行推断出多个 YOLO 类，必须填写人工框；否则检查脚本会阻断训练流水线。

YOLO 类表参考：

```text
data\jade_yolo_class_reference.csv
```

如果不确定 `class_name`，优先填写 `style/theme`，让检查和导入脚本自动推断。

重新生成类表参考：

```powershell
python scripts/generate_jade_yolo_class_reference.py
```

## 2. 先检查 manifest

查看当前流水线状态：

```powershell
python scripts/jade_pipeline_status.py --pretty
```

这个命令只读本地文件，会显示数据集标签数量、反馈记录数量、模型文件、模型卡、交付 zip、JSON/Markdown 评估报告、错判 CSV 和当前缺口。

规划还需要采集哪些样本：

```powershell
python scripts/plan_jade_sample_collection.py --manifest D:\jade\samples.csv --pretty
```

默认目标是每个 YOLO 类至少 20 张、每个颜色/种水/题材至少 10 条；可以用 `--target-per-class` 等参数调整。

训练前可以先做脚本静态自检：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_jade_pipeline_static.ps1
```

静态自检只检查脚本可解析性，不导入样本、不训练。

```powershell
python scripts/check_jade_manifest.py --manifest D:\jade\samples.csv --pretty
```

必须处理阻断问题：

- 图片不存在。
- 图片扩展名不支持。
- `class_name` 不在 YOLO 类表。
- 颜色、种水、样式、题材完全未知。
- 多类别样本没有填写人工框。
- 自动拆分后低于训练门槛。

非阻断提示：

- `noncanonical-*` 表示填写的是别名，导入时会归一成标准标签。

## 3. 一键导入、训练、评估

导入前可以先预览：

```powershell
python scripts/import_jade_feedback_samples.py --manifest D:\jade\samples.csv --dry-run --build-dataset --auto-val
```

`--dry-run` 不复制图片、不写 `data\jade_feedback.jsonl`、不构建数据集，只输出将导入、跳过、重复的统计。

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_jade_training_pipeline.ps1 -Manifest D:\jade\samples.csv
```

推荐首次执行时先跑静态自检：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_jade_training_pipeline.ps1 -Manifest D:\jade\samples.csv -RunStaticCheck
```

流水线会执行：

1. 检查 manifest。
2. 训练前基线评估 `image/text/fused`。
3. 导入人工反馈记录。
4. 构建 YOLO train/val 数据集。
5. 检查训练门槛。
6. 训练 `models/jade-yolo.pt`。
7. 用同一份 manifest 再评估识别准确率。

默认评估报告：

```text
data\jade_eval_baseline.json
data\jade_eval_after_train.json
data\jade_eval_comparison.json
data\jade_eval_summary.md
models\jade-yolo-card.md
```

只检查、导入、评估，不训练：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_jade_training_pipeline.ps1 -Manifest D:\jade\samples.csv -SkipTrain -IncludeRows
```

重复运行同一份 manifest 时，导入脚本默认会按图片来源、人工标签、YOLO 类和框跳过重复样本。只有确实想重复导入作为采样权重时，才单独使用导入脚本的 `--allow-duplicates`。

如果不想输出训练前基线：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_jade_training_pipeline.ps1 -Manifest D:\jade\samples.csv -SkipBaseline
```

## 3.1 从系统反馈复训

如果已经通过前端或接口积累了人工校正反馈，可以直接从 `data\jade_feedback.jsonl` 生成 manifest 并复训：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_jade_feedback_training_pipeline.ps1
```

只导出、检查、评估，不训练：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_jade_feedback_training_pipeline.ps1 -SkipTrain -IncludeRows
```

包含仍待审核的反馈：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_jade_feedback_training_pipeline.ps1 -IncludePending
```

默认导出文件：

```text
data\jade_feedback_manifest.csv
```

## 4. 训练门槛

当前最小门槛：

- `train_labels >= 10`
- `val_labels >= 2`

前端训练 job、训练流水线和 `scripts/train_jade_yolo.py` 都使用同一门槛。手动训练时可用 `--min-train-labels` 和 `--min-val-labels` 调整。

手动从反馈构建 YOLO 数据集时，也建议自动拆分验证集：

```powershell
python scripts/build_jade_yolo_dataset_from_feedback.py --write-yaml --auto-val --val-ratio 0.2
```

手动训练：

```powershell
python scripts/train_jade_yolo.py --write-yaml --min-train-labels 10 --min-val-labels 2
```

实际建议：

- 每个常见类至少 20 张。
- 每张图只有一个明确主体时，整图框可接受。
- 多主体或多题材图片必须填写人工框。
- 颜色和种水不要只靠图片，优先结合主播文本或人工标签。

## 5. 评估结果怎么看

评估脚本会输出：

- `metrics.image.color.accuracy`
- `metrics.image.water.accuracy`
- `metrics.image.style.accuracy`
- `metrics.image.theme.accuracy`
- `metrics.text.color.accuracy`
- `metrics.text.water.accuracy`
- `metrics.text.style.accuracy`
- `metrics.text.theme.accuracy`
- `metrics.fused.color.accuracy`
- `metrics.fused.water.accuracy`
- `metrics.fused.style.accuracy`
- `metrics.fused.theme.accuracy`
- 每个字段的 `confusion`，用于查看常见误判方向
- 可选逐行 `expected / predicted / matches`

单独评估：

```powershell
python scripts/evaluate_jade_manifest.py --manifest D:\jade\samples.csv --mode all --pretty --include-rows
```

保存评估报告：

```powershell
python scripts/evaluate_jade_manifest.py --manifest D:\jade\samples.csv --mode all --pretty --include-rows --output data\jade_eval_manual.json
```

对比训练前后报告：

```powershell
python scripts/compare_jade_eval_reports.py --baseline data\jade_eval_baseline.json --after data\jade_eval_after_train.json --pretty --output data\jade_eval_comparison.json
```

生成 Markdown 摘要：

```powershell
python scripts/summarize_jade_eval_reports.py --output data\jade_eval_summary.md
```

生成模型卡：

```powershell
python scripts/create_jade_model_card.py --output models\jade-yolo-card.md
```

打包模型交付物：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package_jade_model_artifacts.ps1 -RequireModel
```

默认输出：

```text
models\jade-yolo-artifacts.zip
```

检查交付包内容：

```powershell
python scripts/check_jade_artifact_package.py --package models\jade-yolo-artifacts.zip --pretty
```

流水线自动打包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_jade_training_pipeline.ps1 -Manifest D:\jade\samples.csv -PackageArtifacts
```

导出错判样本继续人工复核：

```powershell
python scripts/export_jade_eval_mistakes.py --report data\jade_eval_after_train.json --output data\jade_eval_mistakes.csv --mode all --field all
```

注意：错判导出需要评估报告包含逐行结果，因此运行流水线时建议加 `-IncludeRows`。

流水线自动导出错判样本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_jade_training_pipeline.ps1 -Manifest D:\jade\samples.csv -IncludeRows -ExportMistakes
```

把错判 CSV 转成复核 manifest 草稿：

```powershell
python scripts/create_jade_review_manifest_from_mistakes.py --mistakes data\jade_eval_mistakes.csv --output data\jade_review_manifest.csv
```

这个文件会根据 `style/theme` 尝试推断 `class_name`，但仍只是草稿，必须人工确认 `color/water/style/theme/class_name/box` 后再导入训练。

合并原始 manifest 和人工复核 manifest：

```powershell
python scripts/merge_jade_manifests.py --input D:\jade\samples.csv data\jade_review_manifest.csv --output D:\jade\samples_merged.csv
```

启用质量 gate：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_jade_training_pipeline.ps1 -Manifest D:\jade\samples.csv -FailOnRegression -MinFusedStyle 0.7 -MinFusedTheme 0.7
```

含义：

- `-FailOnRegression`：任一可比较指标比训练前下降，则流水线失败。
- `-MinFusedColor / -MinFusedWater / -MinFusedStyle / -MinFusedTheme`：训练后 fused 准确率最低要求，取值 `0` 到 `1`。

完成标准：

- 本地模型文件存在：`models/jade-yolo.pt`
- manifest 评估能跑完。
- 四个字段有可接受准确率，尤其是 `style/theme` 不能只靠文本命中。
- 前端或接口能使用训练后的 YOLO runtime。

## Single-sample inference

Use this when you want to recognize one jade image before adding it to the training set:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 analyze -Image D:\jade\images\sample.jpg -Text "冰种阳绿观音吊坠" -Output data\jade_single_prediction.json -Pretty
```

The output JSON includes:

- `attributes.color`
- `attributes.water`
- `attributes.style`
- `attributes.theme`
- `confidence`
- `evidence.detections`
- `signals`
- `runtime.yolo`

If the prediction is wrong, add the corrected labels to a manifest row and run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 dry-run-import -Manifest D:\jade\samples.csv
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 import -Manifest D:\jade\samples.csv
```

For batch pre-labeling without requiring corrected labels:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 predict-manifest -Manifest D:\jade\samples.csv -Output data\jade_manifest_predictions.csv -Pretty
```

## Frontend recognition loop

Open the product UI route:

```text
/jade-recognition
```

This page supports the full lightweight loop:

- Upload one or more jade images.
- Add optional anchor speech text.
- Run multimodal recognition for `color / water / style / theme`.
- Review each prediction card.
- Correct wrong fields directly on the card.
- Click `写入反馈训练池` to append the corrected sample to `data/jade_feedback.jsonl`.

After enough corrected samples are saved, rebuild and train:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 train-feedback -RunStaticCheck -IncludeRows -ExportMistakes -PackageArtifacts
```

For offline batch pre-labeling from a manifest, use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 predict-manifest -Manifest D:\jade\samples.csv -Output data\jade_manifest_predictions.csv -Pretty
```

## Offline pre-label to review manifest

When you already have a local image manifest but no corrected labels yet, create predictions first:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 predict-manifest -Manifest D:\jade\samples.csv -Output data\jade_manifest_predictions.csv -Pretty
```

Convert the prediction CSV into a reviewable training manifest:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 predictions-to-manifest -Manifest data\jade_manifest_predictions.csv -Output D:\jade\samples_review.csv
```

If every image is known to contain one clear jade object, you can prefill whole-image YOLO boxes:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 predictions-to-manifest -Manifest data\jade_manifest_predictions.csv -Output D:\jade\samples_review.csv -WholeImageBox
```

Before import, manually review `color / water / style / theme / class_name / box` in `samples_review.csv`. Then run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 dry-run-import -Manifest D:\jade\samples_review.csv
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 import -Manifest D:\jade\samples_review.csv
```

## Batch feedback save

The recognition page also supports saving all corrected cards at once:

```text
/jade-recognition -> 保存全部校正
```

It calls:

```text
POST /api/products/jade-analysis/feedback/batch
```

Each saved item is appended to `data/jade_feedback.jsonl`. If an item maps to exactly one YOLO class and has an image, the backend marks it as `whole-image` training-ready and rebuilds the dataset once after the batch save.

Batch feedback duplicate behavior:

- The frontend skips cards that were already saved in the current page session.
- The backend skips duplicate items inside one batch request when image/text/corrected labels are identical.
- Historical duplicates across sessions are still handled by the import and manifest checking tools before training.

Recognition result review rules:

- Each card shows an attribute source for `color / water / style / theme` when `signals.attribute_sources` is available.
- Low-confidence predictions below `0.45` are marked for manual review.
- Single-card save can still save a low-confidence item after explicit human action.
- Batch save skips low-confidence items when the corrected labels are unchanged from the prediction.

Recognition CSV export:

The `/jade-recognition` page can export the current recognition cards as CSV. The export includes image URL, source filename, text, predicted attributes, corrected attributes, confidence, attribute sources, and saved feedback IDs. Use this file for offline review, sampling audits, and manifest preparation before training.

Recognition to product draft:

The `/jade-recognition` page can create a product draft from any recognition card. Corrected labels take priority over predicted labels. The draft stores color, water, style, theme, size, price, evidence images, evidence text, attribute sources, fusion scores, and a generated selling-point list.

Use this when an operator wants to turn a recognized jade item directly into a product-library item during live operations.

Feedback payload quality rules:

- Single and batch feedback endpoints normalize non-object `input`, `predicted`, `evidence`, and `attribute_sources` to empty objects.
- Evidence `images` and `texts` are normalized to string arrays; invalid detection payloads become an empty list.
- `confidence` is normalized to a float.
- Batch feedback returns `skipped_reasons` so operators can see duplicate rows, missing corrected attributes, or malformed items.
- These guards protect `data/jade_feedback.jsonl` from malformed external clients, but human review is still required before training.

## Active review queue

After batch prediction, select the rows that most need human review:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 select-review-samples -Manifest data\jade_manifest_predictions.csv -Output data\jade_review_queue.csv -ConfidenceThreshold 0.45 -Limit 120
```

The review queue prioritizes:

- prediction errors
- low confidence rows
- missing `color / water / style / theme`
- conflicts between expected and predicted labels
- multi-class rows that need manual YOLO boxes
- rows that have style/theme labels but no mapped YOLO class

Use the queue to decide which samples to correct first, then convert predictions to a review manifest and import after human confirmation.

Recognition page runtime readiness:

The `/jade-recognition` page loads `/api/products/jade-model/status` before recognition. Operators should check this status before trusting image-only predictions:

- `has_jade_yolo_model=false` and `uses_pretrained_yolo_fallback=true` means style/theme detection is relying on a generic YOLO fallback plus rules.
- `has_vlm=false` means complex visual semantics, carving themes, and ambiguous styles need more manual review.
- `has_feedback_learning=false` means historical correction rules are not yet available or not strong enough.

When the page shows a warning, continue using the recognition output as a pre-label, but save corrected samples before training or product use.

Recognition review flags:

Single-sample API, batch API, and `scripts\jade.ps1 analyze` include `review_flags` in recognition payloads. Current flags include:

- `low-confidence`: confidence is below `0.45`.
- `missing-color|water|style|theme`: one or more core jade attributes are missing.
- `no-yolo-detections`: no YOLO detection evidence was returned.
- `no-attribute-sources`: the payload does not contain usable attribute source metadata.

Use these flags to prioritize manual review before saving feedback, creating product drafts, or training.

Review flag implementation:

The shared review flag rules live in:

```text
backend/app/services/jade_review_flags_service.py
```

Both the API recognition payloads and `scripts\jade.ps1 analyze` use this service, so review behavior stays consistent across frontend, CLI, and external integrations.

Offline review flags in prediction CSV:

`predict-manifest` writes a `review_flags` column using the same shared rules as the API and single-sample CLI. Multiple flags are separated by semicolons so compound flags such as `missing-color|water` remain intact.

`select-review-samples` reads this column when available and uses it to prioritize review rows. This keeps API, frontend, CLI, and offline active-review behavior aligned.

Supported upload image formats:

Jade recognition upload endpoints accept these image extensions:

```text
.jpg, .jpeg, .png, .webp, .bmp
```

Files without an extension are treated as `.jpg`. Other formats such as HEIC, video files, archives, or spreadsheets should be converted before upload or added through a reviewed manifest workflow.

Upload size limit:

Jade recognition upload endpoints enforce a per-image limit of 15MB. If source photos are larger, resize or compress them before upload. For training, keep the original high-quality image in your offline archive, but use a reviewed and reasonably compressed copy for web recognition and manifest import.

Upload content validation:

Jade upload endpoints check both the filename extension and the image file header. Renaming a non-image file to `.jpg` is rejected. Supported image headers currently cover JPEG, PNG, WEBP, and BMP.

Batch recognition limits:

The `/jade-recognition` page submits up to 20 images per recognition batch by default. The backend hard limit is 50 images per `/api/products/jade-analysis/batch` request. For larger offline jobs, split the input into multiple batches or use `scripts\jade.ps1 predict-manifest`.

Offline prediction batching:

For large manifests, run `predict-manifest` in chunks with `-Offset` and `-Limit`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 predict-manifest -Manifest D:\jade\samples.csv -Output data\jade_predictions_000.csv -Offset 0 -Limit 50 -Pretty
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 predict-manifest -Manifest D:\jade\samples.csv -Output data\jade_predictions_050.csv -Offset 50 -Limit 50 -Pretty
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 predict-manifest -Manifest D:\jade\samples.csv -Output data\jade_predictions_100.csv -Offset 100 -Limit 50 -Pretty
```

`-Limit` is only passed to `predict-manifest` when explicitly provided, so the default behavior remains full-manifest prediction. Use chunked prediction when images are large, runtime is slow, or you want easier retry behavior.

Merge chunked prediction CSVs:

After chunked prediction, merge prediction CSV files before review selection:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 merge-predictions -Manifest data\jade_predictions_000.csv -SecondaryManifest data\jade_predictions_050.csv -Output data\jade_predictions_000_100.csv
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 merge-predictions -Manifest data\jade_predictions_000_100.csv -SecondaryManifest data\jade_predictions_100.csv -Output data\jade_manifest_predictions.csv
```

The merge tool skips duplicate `row + image + text` records by default. This is useful when retrying failed chunks or combining overlapping batches.

Convert review queue to manifest:

After selecting high-priority rows, generate a reviewable training manifest draft:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 review-queue-to-manifest -Manifest data\jade_review_queue.csv -Output D:\jade\samples_review_queue.csv
```

If each reviewed image contains one clear jade object, prefill whole-image boxes:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 review-queue-to-manifest -Manifest data\jade_review_queue.csv -Output D:\jade\samples_review_queue.csv -WholeImageBox
```

Manually confirm `color / water / style / theme / class_name / box` before importing this manifest into the training pool.

Batch review summary:

Batch recognition responses include `review_summary`, a count of review flags across all returned cards. `predict-manifest` also prints the same summary in its JSON output. Use this summary before manual review:

- High `low-confidence` count means the batch should be reviewed carefully before feedback save.
- High `missing-*` count means the model is not extracting enough complete jade attributes.
- High `no-yolo-detections` count usually means image quality, model availability, or class coverage needs attention.
- High `no-attribute-sources` count means the result lacks explanation metadata and should not be trusted without review.

Runtime limits in model status:

`GET /api/products/jade-model/status` returns a `limits` object for clients:

```json
{
  "upload_image_extensions": [".bmp", ".jpeg", ".jpg", ".png", ".webp"],
  "upload_max_bytes": 15728640,
  "upload_max_mb": 15,
  "batch_max_items": 50,
  "page_default_batch_items": 20
}
```

Frontend and external integrations should read these values instead of hard-coding upload and batch limits.

Recognition batch traceability:

Batch recognition responses include `batch_id`. The `/jade-recognition` page carries this ID through:

- result cards
- CSV export
- feedback save payloads
- product draft evidence text

Use `batch_id` to trace a group of images from recognition, through manual correction, into `data/jade_feedback.jsonl`, exported CSVs, or product-library drafts.

Offline batch traceability:

`predict-manifest` writes a `batch_id` column. If `-BatchId` is not provided, the script creates one automatically. For chunked prediction, pass the same `-BatchId` to every chunk:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 predict-manifest -Manifest D:\jade\samples.csv -Output data\jade_predictions_000.csv -Offset 0 -Limit 50 -BatchId jade-offline-20260603-a
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 predict-manifest -Manifest D:\jade\samples.csv -Output data\jade_predictions_050.csv -Offset 50 -Limit 50 -BatchId jade-offline-20260603-a
```

`select-review-samples`, `predictions-to-manifest`, and `review-queue-to-manifest` preserve this ID in their outputs or review notes, so offline predictions can be traced through review and import.

Batch feedback trace query:

Use the read-only endpoint to inspect feedback records saved from a recognition batch:

```text
GET /api/products/jade-analysis/batches/{batch_id}/feedback
```

The `/jade-recognition` page exposes this as `查询本批反馈`. It reports how many feedback records from the current batch are already in `data/jade_feedback.jsonl`, helping operators confirm that manual corrections were actually saved before training.

CLI batch feedback trace:

Use the CLI to summarize saved feedback records for a recognition batch without opening the frontend:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 batch-feedback -BatchId jade-offline-20260603-a -Pretty
```

Optional JSON output:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 batch-feedback -BatchId jade-offline-20260603-a -Output data\jade_batch_feedback_summary.json -Pretty
```

The summary includes source counts, corrected attribute coverage, YOLO training readiness counts, and record IDs. Use it before `train-feedback` to confirm that the intended batch was actually saved to `data\jade_feedback.jsonl`.

Manifest batch ID column:

Manifest drafts generated from predictions or review queues include a `batch_id` column when available. Keep this column during manual review. It makes it easier to trace a row back to the offline prediction batch and to carry the same trace ID into downstream feedback or training workflows.

Importing batch IDs into feedback:

`import_jade_feedback_samples.py` accepts a per-row `batch_id` manifest column and a shared `--batch-id` argument. Imported feedback records store the ID in `input.batch_id` and also add `batch_id=...` to evidence text. This keeps offline manifest rows traceable after they are appended to `data\jade_feedback.jsonl`.

Exporting feedback manifests with batch IDs:

`export_jade_feedback_manifest.py` includes a `batch_id` column when feedback records contain `input.batch_id` or an evidence text marker like `batch_id=...`. This preserves traceability when exporting `data\jade_feedback.jsonl` back into CSV manifests for review, merging, or retraining.

Export feedback by batch ID:

After saving or importing a traced batch, export only that batch into a manifest:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 export-feedback -BatchId jade-offline-20260603-a -Output data\jade_feedback_manifest_batch.csv
```

Then inspect or train from that batch-specific manifest:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 check -Manifest data\jade_feedback_manifest_batch.csv -Pretty
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 train -Manifest data\jade_feedback_manifest_batch.csv -IncludeRows -ExportMistakes
```

Use this when you want to evaluate or retrain on a specific reviewed batch instead of the entire feedback pool.

Train from one feedback batch:

Use one command to export a batch-specific feedback manifest and run the normal training pipeline:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 train-batch-feedback -BatchId jade-offline-20260603-a -IncludeRows -ExportMistakes
```

To only export/check/evaluate the batch without training:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 train-batch-feedback -BatchId jade-offline-20260603-a -SkipTrain -IncludeRows
```

By default the exported manifest path is `data\jade_feedback_manifest_<batch_id>.csv`. Override it with `-Output` if needed.

Batch feedback summary fields:

The batch feedback trace endpoint returns `summary` with:

- `attribute_counts`: how many saved feedback records contain corrected `color / water / style / theme`.
- `training_counts.yolo_ready`: records with mapped YOLO classes.
- `training_counts.requires_manual_box`: records that need manual boxes before YOLO training.
- `training_counts.whole_image_box`: records ready as whole-image training samples.
- `training_counts.manual_box`: records already carrying manual YOLO boxes.
- `source_counts`: feedback sources in the batch.

The `/jade-recognition` page shows these counts after `查询本批反馈`, so operators can decide whether the batch is ready for `train-batch-feedback`.

Batch feedback readiness recommendations:

The batch feedback trace `summary.readiness` gives a conservative next-step recommendation before batch training:

- `can_try_batch_training`: true only when the batch has enough YOLO-ready records, no manual boxes are required, and all core attributes have some coverage.
- `minimum_yolo_ready_records`: currently 12, leaving room for train/val splitting.
- `blocking_reasons`: why the batch is not ready yet.
- `recommended_next_steps`: operator actions such as saving corrected feedback, adding boxes, completing labels, or running `train-batch-feedback`.

This readiness check is a pre-training guide. It does not prove that model training will pass or that recognition quality is good enough; evaluation reports and real sample tests are still required.

CLI batch feedback readiness:

`scripts\jade.ps1 batch-feedback` now includes the same `readiness` object as the API batch trace endpoint. Use `readiness.can_try_batch_training`, `blocking_reasons`, and `recommended_next_steps` to decide whether to run `train-batch-feedback` from the command line.

Batch readiness implementation:

The shared batch feedback summary and readiness rules live in:

```text
backend/app/services/jade_batch_feedback_summary_service.py
```

Both the API endpoint `GET /api/products/jade-analysis/batches/{batch_id}/feedback` and CLI command `scripts\jade.ps1 batch-feedback` use this service, keeping batch training recommendations consistent across frontend and offline workflows.

Frontend batch training command hint:

After `查询本批反馈`, the `/jade-recognition` page can generate a copyable `train-batch-feedback` command for the current `batch_id`. If readiness says the batch can try training, the command includes `-IncludeRows -ExportMistakes`. If readiness is blocked, the generated command adds `-SkipTrain` so operators can safely export/check/evaluate the batch without starting YOLO training.

Frontend command display:

The `/jade-recognition` page displays the generated `train-batch-feedback` command in a code block after batch feedback readiness is available. The copy button uses the browser clipboard API; if clipboard access is blocked, copy the command manually from the code block.

Product draft batch trace metadata:

Product drafts created from `/jade-recognition` include batch trace metadata in two places:

- `evidence_texts` contains `batch_id=...`.
- `attribute_sources._trace` contains the same batch ID with source `jade-recognition-page` and method `batch-trace`.

This lets operators trace a product-library draft back to the recognition batch that created it.

Prediction row numbering with offset:

When `predict-manifest` is run with `-Offset`, the output CSV `row` column keeps the original manifest row number. For example, `-Offset 50 -Limit 50` writes rows starting at 51. This keeps chunked prediction, merge, review queues, and manifest conversion traceable back to the original source manifest.

Merge multiple prediction chunks at once:

`merge-predictions` accepts comma-separated additional CSVs through `-SecondaryManifest`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\jade.ps1 merge-predictions -Manifest data\jade_predictions_000.csv -SecondaryManifest "data\jade_predictions_050.csv,data\jade_predictions_100.csv,data\jade_predictions_150.csv" -Output data\jade_manifest_predictions.csv
```

The first `-Manifest` is kept as the first input, and all comma-separated secondary files are merged in order.

`train-batch-feedback -Output` behavior:

For `train-batch-feedback`, `-Output` overrides the exported batch manifest CSV path, not the model output directory. The command prints both `BatchId` and `Batch manifest` before running the training pipeline so operators can inspect or reuse the exported CSV.

Readiness threshold in model status:

`GET /api/products/jade-model/status` includes `limits.batch_readiness_min_yolo_ready_records`, sourced from `backend/app/services/jade_batch_feedback_summary_service.py`. The frontend displays this value so operators know how many YOLO-ready feedback records a batch should have before trying `train-batch-feedback`.

Batch trace implementation:

The shared batch ID extraction and matching rules live in:

```text
backend/app/services/jade_batch_trace_service.py
```

API batch feedback queries, `export-feedback -BatchId`, and `batch-feedback -BatchId` all use this service. This keeps `input.batch_id` and evidence text marker `batch_id=...` matching behavior consistent.

Import summary batch counts:

`import_jade_feedback_samples.py` returns `batch_counts` in its JSON summary. Use it to confirm how many imported records were written per `batch_id`. Records without a batch ID are grouped under `(none)`.

Import summary batch training counts:

`import_jade_feedback_samples.py` also returns `batch_training_counts`, grouped by `batch_id`. Each batch shows `records`, `yolo_ready`, `requires_manual_box`, `whole_image_box`, and `manual_box`. Use it after import or dry-run import to decide whether a batch is ready for dataset building or still needs manual YOLO boxes.

Import batch training count implementation:

`import_jade_feedback_samples.py` keeps the existing `batch_training_counts` output shape, but computes per-batch training counts through `summarize_jade_batch_feedback`. This aligns import summaries with API batch feedback traces and CLI `batch-feedback` summaries.

Import summary batch readiness:

`import_jade_feedback_samples.py` returns `batch_readiness` for each imported batch. This uses the same shared readiness rules as API batch feedback traces and CLI `batch-feedback`. After import or dry-run import, check `batch_readiness.<batch_id>.can_try_batch_training`, `blocking_reasons`, and `recommended_next_steps` before running `train-batch-feedback`.

Import batch grouping consistency:

`batch_counts`, `batch_training_counts`, and `batch_readiness` in the import summary all use the same `input.batch_id` grouping. Records without a batch ID are grouped as `(none)`.

## Manifest merge batch trace

When combining multiple reviewed manifests, `scripts\jade.ps1 merge-manifests` preserves the `batch_id` column so merged training CSVs can still be filtered, exported, and trained by batch.


## Image model attribute mapping

The image recognizer maps YOLO class labels and VLM JSON output into the same canonical Chinese attributes used by feedback and training: color, water, style, and theme. YOLO is used for detected shape/theme labels, VLM can fill all four fields, and OpenCV heuristics only fill missing color/water/style values as weak evidence.


## VLM output normalization

VLM output parsing accepts plain JSON, Markdown fenced JSON, and nested payloads such as `attributes`/`result`/`analysis`. Field aliases like `颜色`/`color_name`, `种水`/`seed`, `器型`/`shape`, and `题材`/`subject` are normalized into the canonical `color`/`water`/`style`/`theme` attributes before feedback and training export.


VLM parsers also accept top-level JSON arrays and object-valued fields such as `{"color": {"value": "阳绿"}}` or list-valued fields such as `{"theme": ["观音"]}`. The first valid object/value is used, then normalized into canonical jade attributes.

When a VLM returns descriptive fields such as `name`, `title`, `description`, `caption`, `summary`, or `text` instead of explicit attribute fields, the parser uses the description as a fallback source. It extracts canonical color/water/style/theme terms from that text only for fields that are still empty, preserving explicit structured model output when present.

If a VLM returns plain descriptive text with no JSON object and no labeled fields, such as `白冰冰种观音吊坠`, the parser falls back to keyword extraction over the whole response. This fallback only runs after structured JSON and labeled fields fail to produce any attributes.

## Parser verification gate

`backend/tests/test_jade_model_parsing.py` covers the core parser expectations for VLM Markdown JSON, nested attributes, plain VLM descriptions, description fallback behavior, and YOLO label-to-style/theme mapping. Before claiming the jade recognizer is complete, run this test file together with the broader backend and frontend checks.

VLM normalization does not rely only on feedback cleanup rules. Structured values are first cleaned, then mapped through the VLM parser's local canonical jade term catalogs so aliases such as `正阳绿`, `糯冰种`, and `挂件` resolve to stable training labels like `阳绿`, `糯冰`, and `吊坠`.

The parser verification test file also includes a multimodal fusion contract: text-derived color/water and image-derived style/theme must merge into one complete jade analysis without requiring live model inference. This test is a minimum gate before any end-to-end recognizer claim.

## Offline recognition examples

`data/jade_recognition_examples.jsonl` contains a small fixed set of jade recognition examples covering text extraction, VLM Markdown JSON, VLM plain descriptions, YOLO label mapping, and multimodal fusion expectations. These examples are useful for parser tests, demos, and manual acceptance checks, but they do not replace real jade image evaluation with actual model/runtime output.

## Offline example checker

`scripts/check_jade_recognition_examples.py` reads `data/jade_recognition_examples.jsonl` and checks parser/fusion outputs against expected color/water/style/theme values. It is intended as a fast local acceptance gate for text parsing, VLM parsing, YOLO label mapping, and multimodal fusion. It does not invoke real image models, does not read real jade images, and must be followed by model/runtime evaluation before the recognizer can be considered complete.

Example command when validation is allowed:

```powershell
python scripts\check_jade_recognition_examples.py --pretty
```

On Windows/PowerShell, the same offline example checker can be launched through:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_jade_recognition_examples.ps1 -Pretty
```

This wrapper exists so operators can run the parser/fusion acceptance gate without remembering Python script arguments.

The offline example checker treats malformed JSONL rows as failed records. Fusion examples may provide the detection label either at `input.label` or `input.image_attributes.label`; the checker includes that label in the synthetic image-side detection evidence while still avoiding real model inference.

For fusion examples, `input.image_attributes.label` is treated as detection evidence metadata, not as a canonical jade attribute. The checker reads it before reducing image attributes to color/water/style/theme.

`backend/tests/test_jade_recognition_examples_checker.py` imports the offline checker and asserts every record in `data/jade_recognition_examples.jsonl` matches its expected attributes. This test should be run with the parser tests before relying on the offline acceptance examples.

`backend/tests/test_jade_text_recognition.py` covers the baseline Chinese text recognizer: direct descriptions must extract color/water/style/theme, plus size and price when present. This is a required foundation because VLM descriptions, OCR text, and live speech all reuse the same jade text semantics.

## Acceptance gates

`data/jade_recognition_acceptance_gates.json` is the machine-readable completion checklist for the jade recognizer. It separates offline gates (text recognition, VLM/YOLO parsing, fixed examples) from runtime gates (batch upload API, real labeled image evaluation, and feedback/training loop). The recognizer should not be marked complete until the offline gates pass and the runtime gates are proven with current command output or rendered/API evidence.

For semi-structured VLM text such as `颜色: 蓝水。整体像高冰龙牌`, labeled values are parsed first and the full response text is then used only to fill still-empty attributes. This preserves explicit model fields while improving recall for water/style/theme mentions in the surrounding description.

Semi-structured VLM labeled fields stop at common Chinese and English separators, including commas, semicolons, full stops, enumeration commas, question marks, exclamation marks, and newlines. This prevents a value such as `颜色: 蓝水。整体像高冰龙牌` from treating the whole remaining sentence as the color value while still using the remaining response text to fill empty attributes.

The semi-structured VLM label parser uses real regex whitespace matching around `:`/`：` delimiters, so forms like `颜色 : 蓝水` and `颜色: 蓝水` are both accepted. Separator handling remains bounded so labeled values do not consume the rest of the response.

## Unified offline gate runner

`scripts/check_jade_recognition_offline_gates.ps1` runs the minimum offline acceptance suite in one step: text recognition tests, VLM/YOLO parser tests, offline example checker tests, and the JSONL example checker. This is still not a runtime model evaluation; it only proves the parser/fusion contract when validation is allowed.

Example command when validation is allowed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_jade_recognition_offline_gates.ps1 -Pretty
```

## Real image manifest readiness

Before running real jade image evaluation, use `scripts/check_jade_manifest_readiness.ps1` to confirm the labeled manifest has image paths, existing image files, and the required `color`/`water`/`style`/`theme` labels. This is a preflight check for runtime evaluation, not a recognizer accuracy test.

Example command when validation is allowed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_jade_manifest_readiness.ps1 -Manifest data\jade_sample_manifest_template.csv -Pretty
```

Manifest readiness accepts canonical labels and common review/evaluation aliases: `color`/`expected_color`/`corrected_color`/`actual_color`, the same pattern for `water`/`style`/`theme`, plus Chinese headers such as `颜色`, `种水`, `样式`, and `题材`. This lets reviewed, predicted, and corrected manifests pass the same preflight check before real image evaluation.

The unified offline gate runner sets `PYTHONPATH` to include the local `backend` directory before invoking pytest. This keeps parser/fusion tests independent of the caller's shell environment and avoids accidental `app` import failures when running from PowerShell.

The unified offline gate runner now has a cross-platform Python entrypoint: `scripts/check_jade_recognition_offline_gates.py`. The PowerShell script is a thin Windows wrapper around that Python runner, so the test/check list is maintained in one place.

Cross-platform command when validation is allowed:

```powershell
python scripts\check_jade_recognition_offline_gates.py --pretty
```

## Batch recognition API smoke gate

`scripts/check_jade_batch_api.py` and `scripts/check_jade_batch_api.ps1` are runtime smoke checks for `/api/products/jade-analysis/batch`. They upload one or more real image files to a running backend and verify that the response item count, confidence field, signals, review flags, and canonical `color`/`water`/`style`/`theme` payload shape are present. Use `--require-all-attributes` / `-RequireAllAttributes` when the supplied images are labeled enough that every field should be populated.

Example command when the backend is running and validation is allowed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_jade_batch_api.ps1 -Image data\samples\jade1.jpg,data\samples\jade2.jpg -Text "白冰冰种观音吊坠" -Pretty
```

This smoke gate proves API payload shape and live upload flow. It still does not replace labeled real-image accuracy evaluation.

## Synthetic smoke images

`scripts/create_jade_smoke_images.py` and `scripts/create_jade_smoke_images.ps1` generate a tiny local PNG set plus `data/generated_jade_smoke_manifest.csv`. The images are synthetic bangle/pendant/plaque shapes with labeled color/water/style/theme expectations. They are intended for upload/API smoke checks when no safe real jade images are available, not for model accuracy claims.

Example commands when validation is allowed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\create_jade_smoke_images.ps1 -Pretty
powershell -ExecutionPolicy Bypass -File scripts\check_jade_batch_api.ps1 -Image data\generated_jade_smoke_images\smoke-white-ice-pendant.png,data\generated_jade_smoke_images\smoke-green-bangle.png,data\generated_jade_smoke_images\smoke-blue-dragon-plaque.png -Text "白冰冰种观音吊坠；阳绿糯冰手镯；蓝水高冰龙牌" -Pretty
```

The batch API smoke checker can upload images from a manifest directly. Use `--manifest` / `-Manifest` with any CSV/JSON/JSONL containing `image`/`image_path`/`path`; if `--text` / `-Text` is not provided, text-like columns such as `text`, `context_text`, `description`, `title`, or `name` are joined as context.

Manifest-driven synthetic smoke example when the backend is running and validation is allowed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\create_jade_smoke_images.ps1 -Pretty
powershell -ExecutionPolicy Bypass -File scripts\check_jade_batch_api.ps1 -Manifest data\generated_jade_smoke_manifest.csv -Pretty
```

`backend/tests/test_jade_batch_api_smoke_helpers.py` covers the batch API smoke checker's offline helper logic: manifest image/text extraction, successful response payload inspection, and blocking behavior when required attributes are missing. This is included in the unified offline gate runner, but it does not call a running backend; the runtime API smoke gate still must be executed separately with real or synthetic image files.

## Feedback readiness gate

`scripts/check_jade_feedback_readiness.py` and `scripts/check_jade_feedback_readiness.ps1` inspect `data/jade_feedback.jsonl` before training/export. They check matching record count, corrected `color`/`water`/`style`/`theme`, batch id presence, image/text evidence, and whether records have box data for YOLO-style training. This is a preflight check for the human-correction/training loop; it does not export, train, or evaluate a model.

Example command when validation is allowed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_jade_feedback_readiness.ps1 -BatchId "jade-analysis-batch-..." -Pretty
```

`backend/tests/test_jade_feedback_readiness.py` covers the feedback readiness helper logic: corrected color/water/style/theme extraction, prediction extraction, batch_id extraction from `input.batch_id` and `evidence_texts`, plus image/text/box evidence detection. It is included in the unified offline gate runner, but it does not export, train, or evaluate a model.

Feedback readiness accepts both nested feedback payloads (`corrected`, `corrected_attributes`, `expected`, `actual`, `prediction`, `predicted`, `analysis`) and flat fields such as `corrected_color`, `expected_water`, `actual_style`, and `predicted_theme`. This keeps the preflight check compatible with API feedback records, exported review CSV rows converted to JSONL, and training manifests.

## Prediction result gate

`scripts/check_jade_prediction_results.py` and `scripts/check_jade_prediction_results.ps1` inspect prediction CSV output after real image evaluation. They compute per-attribute prediction coverage for `color`/`water`/`style`/`theme`, and exact-match accuracy when expected labels are present. This gate reads prediction results only; it does not run inference, train, or evaluate images by itself.

Example command when a prediction CSV exists and validation is allowed:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_jade_prediction_results.ps1 -Predictions data\jade_predictions.csv -MinCoverage 0.8 -MinAccuracy 0.6 -Pretty
```

`backend/tests/test_jade_prediction_results.py` covers prediction CSV gate helper logic: per-attribute coverage, exact-match accuracy, complete prediction rows, complete expected rows, and fallback columns such as `actual_water`, `label_style`, and `corrected_theme`. It is included in the unified offline gate runner, but it does not run inference or produce prediction CSVs.

## Synthetic smoke image generator gate

The offline gate runner now includes `backend/tests/test_jade_smoke_images.py`. This test imports `scripts/create_jade_smoke_images.py`, renders one synthetic jade sample, writes it as PNG, and checks the PNG signature/chunks without requiring PIL, OpenCV, network access, or a model runtime.

Use this gate before runtime API smoke testing to prove the local synthetic-image fixtures can be generated for `/api/products/jade-analysis/batch` checks:

```powershell
.\scripts\check_jade_recognition_offline_gates.ps1 -Pretty
```

This does not prove recognition accuracy. It only protects the fixture generator used by the later multimodal API smoke and real-image evaluation gates.

## Jade taxonomy contract gate

The offline gate runner now includes `backend/tests/test_jade_taxonomy_contract.py`. This protects the minimum production taxonomy required by the multimodal jade recognizer:

- color: `����`, `������`, `��ˮ`, `������`, `����`, `�ױ�`
- water: `������`, `����`, `�߱�`, `Ŵ��`, `����`
- style: `����`, `�鴮`, `����`, `��׹`, `��ָ`, `����`, `ƽ����`, `�ڼ�`
- theme: `����`, `��`, `����`, `Ҷ��`, `ɽˮ`, `����`, `����`, `����`

The same gate also checks a text-recognition contract example: `���̱��ֹ�����׹` must resolve to `color=����`, `water=����`, `style=��׹`, and `theme=����`. This keeps the core business fields stable while image heuristics, YOLO labels, and VLM parsing evolve.

## Saved batch API response contract gate

Use `scripts/check_jade_api_response_contract.py` to audit a saved JSON response from `/api/products/jade-analysis/batch` without calling the backend again. This is useful after manual browser/API smoke testing because it turns the captured response into repeatable evidence.

```powershell
.\scripts\check_jade_api_response_contract.ps1 -Response .\tmp\jade-batch-response.json -RequireAllAttributes -Pretty
```

The checker accepts response shapes such as a top-level array or objects containing `results`, `items`, `data`, or `records`. Each result must expose:

- `color`, `water`, `style`, `theme`
- `confidence`
- `signals`
- `review_flags`

`-RequireAllAttributes` also fails empty `color/water/style/theme` values. This gate does not call the model and does not prove image-recognition accuracy; it proves the runtime API response still carries the fields required by the jade recognition workflow and frontend review loop.

### Nested saved response support

The saved API response contract checker also accepts runtime fields from nested recognizer payloads. `confidence`, `signals`, and `review_flags` may be located on the result item itself or inside nested `result`, `analysis`, `attributes`, `jade`, or `prediction` objects. This keeps the audit stable if the backend wraps the jade analysis before returning it to the frontend.

## Real jade image labeling manifest

Use `scripts/create_jade_labeling_manifest.py` to turn a directory of real jade images into a CSV labeling template. The template is designed for the required multimodal recognition fields: `color`, `water`, `style`, and `theme`.

```powershell
.\scripts\create_jade_labeling_manifest.ps1 `
  -ImageDir .\data\real_jade_images `
  -Output .\data\real_jade_labeling_manifest.csv `
  -Recursive `
  -RelativeTo .\data `
  -BatchId real-jade-001
```

The generated CSV columns are:

- `image_path`
- `text`
- `color`
- `water`
- `style`
- `theme`
- `notes`
- `batch_id`

Fill the blank label fields manually, then use the existing manifest readiness and evaluation gates to check whether the recognizer can predict the labeled `color/water/style/theme` values from images and optional text context.

## Labeled manifest distribution gate

After filling a real jade labeling manifest, run the label distribution gate before evaluation. This catches empty or overly narrow labels for the four required recognition fields.

```powershell
.\scripts\check_jade_label_distribution.ps1 `
  -Manifest .\data\real_jade_labeling_manifest.csv `
  -MinLabeled 20 `
  -MinDistinctPerAttribute 3 `
  -Pretty
```

The checker supports CSV, JSON, and JSONL manifests and reports per-attribute counts for:

- `color`
- `water`
- `style`
- `theme`

Use stricter thresholds for model evaluation datasets than for quick smoke sets. For example, a production evaluation set should include multiple colors, multiple water grades, several styles, and multiple themes, otherwise aggregate accuracy will be misleading.

## Human review queue from saved recognition response

After saving a `/api/products/jade-analysis/batch` response, create a human review queue for weak or incomplete jade recognition rows:

```powershell
.\scripts\create_jade_review_queue.ps1 `
  -Response .\tmp\jade-batch-response.json `
  -Output .\data\jade_review_queue.csv `
  -MinConfidence 0.65
```

Rows are queued when any of the required fields are missing, confidence is below the threshold, confidence is invalid, or `review_flags` are present. The review CSV includes:

- `image_path`
- `text`
- `color`
- `water`
- `style`
- `theme`
- `confidence`
- `review_reasons`
- `review_flags`
- `batch_id`

Use this CSV for manual correction, then convert the reviewed rows into feedback or a labeled manifest so corrections can flow back into the training and evaluation loop.

## Convert reviewed queue to feedback JSONL

After manually correcting `color`, `water`, `style`, and `theme` in a review queue CSV, convert the reviewed rows into feedback JSONL:

```powershell
.\scripts\convert_jade_review_queue_to_feedback.ps1 `
  -ReviewQueue .\data\jade_review_queue.csv `
  -Output .\data\jade_review_feedback.jsonl `
  -RequireComplete `
  -PrettySummary
```

The converter writes records with:

- `input.image_path`, `input.text`, `input.batch_id`
- `prediction.color/water/style/theme` when predicted columns are available
- `corrected.color/water/style/theme` from corrected, actual, expected, or current label columns
- review metadata and `evidence_texts` including `batch_id=...`

Use `-RequireComplete` for training feedback so incomplete manual corrections are skipped instead of entering the learning loop. The generated JSONL can then be checked with the feedback readiness gate and used by the existing batch-feedback training flow.

## Stable train/eval split for labeled jade manifests

After the real jade labeling manifest passes readiness and label-distribution gates, split it into stable train and eval CSV files. Keep the eval split fixed so later model or prompt changes can be compared against the same held-out images.

```powershell
.\scripts\split_jade_manifest.ps1 `
  -Manifest .\data\real_jade_labeling_manifest.csv `
  -TrainOutput .\data\jade_train_manifest.csv `
  -EvalOutput .\data\jade_eval_manifest.csv `
  -EvalRatio 0.2 `
  -Salt jade-v1 `
  -RequireComplete `
  -PrettySummary
```

The splitter uses a stable hash of each row's image/text identity and writes a `split` column. `-RequireComplete` skips rows missing any of the required recognition labels: `color`, `water`, `style`, or `theme`.

Use the train split for feedback/training flows and the eval split for prediction-result gates. Do not tune thresholds or prompts directly on the eval split unless you intentionally rotate to a new salt and record that change.

## Train/eval split integrity gate

After splitting labeled jade manifests, check that train and eval do not share the same image/text identity. This protects the real-image evaluation from leakage.

```powershell
.\scripts\check_jade_split_integrity.ps1 `
  -Train .\data\jade_train_manifest.csv `
  -Eval .\data\jade_eval_manifest.csv `
  -Pretty
```

The checker reports:

- train/eval overlap
- duplicate train rows
- duplicate eval rows

Run this before prediction-result evaluation. If overlap exists, regenerate the split with a stable manifest and do not use the leaked eval results as accuracy evidence.

## VLM training JSONL export

After the labeled jade train split is ready, export image-grounded VLM training records. Each row becomes a multimodal user message with the image path and prompt, plus an assistant JSON answer containing `color`, `water`, `style`, and `theme`.

```powershell
.\scripts\create_jade_vlm_training_jsonl.ps1 `
  -Manifest .\data\jade_train_manifest.csv `
  -Output .\data\jade_vlm_train.jsonl `
  -PrettySummary
```

The output JSONL includes:

- `image`
- `messages[0]` as a user multimodal prompt with image and text
- `messages[1]` as an assistant JSON answer
- `attributes.color/water/style/theme`
- `batch_id` when available

By default, rows missing any required label are skipped. Use this export for VLM fine-tuning, prompt-evaluation fixtures, or offline review of whether the labeled image dataset can train the recognizer to produce the same four business fields used by the frontend and API.

## VLM training JSONL contract gate

After exporting `jade_vlm_train.jsonl`, check that every multimodal training record has an image, a user image message, and an assistant JSON answer with the four required jade fields:

```powershell
.\scripts\check_jade_vlm_training_jsonl.ps1 `
  -Input .\data\jade_vlm_train.jsonl `
  -Pretty
```

The gate checks:

- top-level `image`
- user message contains image content
- assistant content parses as JSON
- assistant JSON contains `color`, `water`, `style`, and `theme`

This gate does not inspect image bytes and does not call a model. It only proves the exported JSONL is structurally usable for VLM fine-tuning or offline multimodal prompt evaluation.

## Manifest image path gate

Before running batch recognition, train/eval splitting, prediction evaluation, or VLM JSONL export, check that every manifest image path points to a local file:

```powershell
.\scripts\check_jade_manifest_images.ps1 `
  -Manifest .\data\real_jade_labeling_manifest.csv `
  -BaseDir .\data `
  -Pretty
```

The checker supports CSV, JSON, and JSONL manifests. It accepts image path fields named `image_path`, `image`, or `path`, including nested `input.image_path` records from feedback-style JSON.

The gate reports:

- rows with missing image paths
- image paths that do not exist on disk
- present image count

Run this before using a manifest as evidence for multimodal recognition quality. Missing images make both API smoke checks and accuracy reports invalid.

## Prediction error summary

After running prediction-result evaluation on the held-out jade eval split, summarize the concrete mistakes by attribute:

```powershell
.\scripts\summarize_jade_prediction_errors.ps1 `
  -Predictions .\data\jade_eval_predictions.csv `
  -MaxExamples 30 `
  -Pretty
```

The report groups mistakes for:

- `color`
- `water`
- `style`
- `theme`

For each attribute it reports compared rows, correct rows, accuracy, missing predictions, confusion pairs such as `expected=����` and `predicted=Ŵ��`, and example rows. Use this after the accuracy gate to decide whether the next improvement should focus on color taxonomy, water-grade discrimination, object style detection, or theme/motif recognition.

## Prediction errors to review queue

After evaluating held-out jade predictions, convert mismatched rows into a human review queue. This lets eval mistakes flow back into manual correction and feedback training.

```powershell
.\scripts\create_jade_error_review_queue.ps1 `
  -Predictions .\data\jade_eval_predictions.csv `
  -Output .\data\jade_eval_error_review_queue.csv
```

The queue includes predicted values and expected/corrected labels for:

- `color`
- `water`
- `style`
- `theme`

Rows are included when any expected label differs from the predicted value. The output can be manually reviewed, then passed through `convert_jade_review_queue_to_feedback.ps1` to create feedback JSONL for the learning loop.

## Confidence calibration summary

After prediction evaluation, summarize accuracy by confidence bucket. This helps choose review thresholds instead of relying on a fixed arbitrary confidence cutoff.

```powershell
.\scripts\summarize_jade_confidence_calibration.ps1 `
  -Predictions .\data\jade_eval_predictions.csv `
  -BucketSize 0.1 `
  -Pretty
```

The report groups rows by confidence and reports per-bucket accuracy for:

- `color`
- `water`
- `style`
- `theme`
- complete four-field exact match

Use this with the prediction error summary. If low-confidence buckets are inaccurate, increase automatic review coverage. If high-confidence buckets still contain many water or theme errors, improve that recognizer path instead of simply changing the confidence threshold.

## Gate report summary

After running offline, runtime, manifest, prediction, and feedback gates, summarize their saved JSON outputs into one acceptance overview:

```powershell
.\scripts\summarize_jade_gate_reports.ps1 `
  -Report .\tmp\offline-gates.json, .\tmp\manifest-images.json, .\tmp\prediction-results.json, .\tmp\feedback-readiness.json `
  -Pretty
```

The summary infers `ok`, `failed`, or `unknown` from each report's `status`, `returncode`, or nested `steps`. It also counts common evidence fields such as `issues`, `errors`, and `skipped`.

Use this as the final evidence index for the jade multimodal recognition workflow. It does not replace the individual gates; it makes their outputs easier to audit together before deciding whether color, water, style, and theme recognition is ready for production use.

## Source agreement summary

After saving a batch recognition response, summarize whether individual sources agree with the final fused jade attributes:

```powershell
.\scripts\summarize_jade_source_agreement.ps1 `
  -Response .\tmp\jade-batch-response.json `
  -MaxExamples 30 `
  -Pretty
```

The report counts available sources such as text, image, VLM, YOLO, heuristic, vision, or OCR blocks, then compares each source's `color`, `water`, `style`, and `theme` against the final fused result.

Use this when accuracy is low but it is unclear where the failure starts. If source conflicts concentrate in VLM water grades, improve VLM prompting/training. If YOLO style conflicts dominate, improve object labels. If text and image disagree often, review the fusion priority and review-flag rules.
