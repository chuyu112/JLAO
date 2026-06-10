# JLAO 项目交接清单

> **日期**：2026-06-10
> **交接人**：Worker A
> **接收人**：新电脑
> **项目**：翡翠直播间 AI 识别系统

---

## 一、打包文件

| 文件 | 大小 | 说明 |
|---|---|---|
| `jade_training_backup_20260610.tar.gz` | **788 MB** | 训练数据 + 模型 + 脚本 |

## 二、文件内容

### 1. 训练数据（data/jade_yolo/）

```
data/jade_yolo/
├── dataset.yaml          # YOLO 数据集配置
├── classes.txt           # 14 个类别名称
├── empty_labels.txt      # 空标注文件列表
├── images/
│   ├── train/            # 训练集（450 张）
│   ├── val/              # 验证集（113 张）
│   └── test/             # 测试集（空）
└── labels/
    ├── train/            # 训练标注（384 张有效）
    ├── val/              # 验证标注
    └── classes.txt       # 类别映射
```

**标注统计：**
- 总图片：450 张（训练）+ 113 张（验证）
- 有效标注：384 张
- 空标注：66 张（可作为负样本）

### 2. 模型文件（models/）

| 模型 | 说明 |
|---|---|
| `jade-yolo.pt` | 当前最佳模型（YOLO11n） |
| `jade-yolo.before-*.pt` | 历史备份 |
| `yolo11n.pt` | 基础模型 |

### 3. 训练记录（runs/jade-yolo/）

```
runs/jade-yolo/
├── jade-yolo/            # 第一次训练（50 epochs）
│   ├── weights/best.pt
│   └── results.png
└── jade-yolo-2/          # 第二次训练（100 epochs）
    ├── weights/best.pt
    └── results.png
```

### 4. 训练脚本

| 脚本 | 用途 |
|---|---|
| `scripts/train_jade_yolo.py` | 训练主脚本 |
| `scripts/auto_label_yolo.py` | 自动标注 |
| `scripts/check_label_quality.py` | 标注质量检查 |
| `scripts/generate_jade_variations_v3.py` | AI 图生图 |
| `scripts/organize_ai_variations.py` | 数据整理 |

---

## 三、类别分布

| 类别 | 数量 | 状态 |
|---|---|---|
| jade_bangle (手镯) | 326 | ✅ 充足 |
| jade_pendant (吊坠) | 95 | ⚠️ 需补充 |
| jade_cabochon (蛋面) | 78 | ⚠️ 需补充 |
| jade_beads (珠串) | 57 | ⚠️ 需补充 |
| pingan_kou (平安扣) | 55 | ⚠️ 需补充 |
| jade_ring (戒指) | 46 | ⚠️ 需补充 |
| guanyin (观音) | 38 | ⚠️ 需补充 |
| buddha (佛公) | 36 | ⚠️ 需补充 |
| ruyi (如意) | 14 | ⚠️ 需补充 |
| jade_plaque (牌子) | ? | ❌ 需收集 |
| leaf (叶子) | ? | ❌ 需收集 |
| landscape (山水) | ? | ❌ 需收集 |
| pixiu (貔貅) | ? | ❌ 需收集 |
| gourd (葫芦) | ? | ❌ 需收集 |

**目标**：每个品类 200 张标注图片

---

## 四、新电脑部署步骤

### 1. 解压数据

```bash
# 复制到 D:\JLAO
cp jade_training_backup_20260610.tar.gz D:\JLAO\

# 解压
cd D:\JLAO
tar -xzvf jade_training_backup_20260610.tar.gz
```

### 2. 配置环境

```bash
# 创建虚拟环境
cd D:\JLAO\backend
python -m venv .venv-local

# 安装依赖
.venv-local\Scripts\pip install -r requirements.txt

# 安装 ultralytics
.venv-local\Scripts\pip install ultralytics
```

### 3. 验证数据

```bash
# 检查训练数据
python scripts/check_label_quality.py

# 测试模型
python -c "from ultralytics import YOLO; model = YOLO('models/jade-yolo.pt')"
```

### 4. 继续训练

```bash
# 训练命令
python scripts/train_jade_yolo.py --epochs 100 --batch auto
```

---

## 五、重要配置

### API 配置（scripts/generate_jade_variations_v3.py）

```python
api_key = "sk-REDACTED"
base_url = "http://api.kakayiduo.cloud:8080/v1"
```

### 服务器信息

| 项目 | 值 |
|---|---|
| 服务器 IP | 47.120.41.143 |
| 域名 | jlao.szkakayiduo.com |
| 后端端口 | 8001 |
| Redis | 47.120.41.143:6379 |

---

## 六、注意事项

1. **数据备份**：定期备份 `data/jade_yolo/` 和 `models/`
2. **GitHub**：代码已上传，数据未上传（太大）
3. **双图问题**：AI 生成的图片是左右双图，下次生成时裁剪成单图
4. **类别不平衡**：手镯数据过多，其他品类需补充

---

## 七、下一步计划

1. **补充数据**：每个品类生成到 200 张
2. **裁剪图片**：处理双图问题
3. **重新训练**：平衡数据集后训练
4. **测试模型**：验证识别效果

---

**交接完成！**
