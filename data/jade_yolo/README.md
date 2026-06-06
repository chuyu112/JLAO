# 翡翠 YOLO 数据集约定

这个目录用于训练 `models/jade-yolo.pt`。前期可以先用 YOLO 小模型预训练权重微调，样本少时先跑“弱标注”版本；后续你提供更精确的翡翠标注图后，再逐步替换成精标数据。

## 目录结构

```text
data/jade_yolo/
  dataset.yaml
  images/train/
  images/val/
  images/test/
  labels/train/
  labels/val/
  labels/test/
```

## 类别

```text
0  jade_bangle    手镯
1  jade_beads     珠串 / 手串 / 珠链
2  jade_cabochon  蛋面 / 戒面
3  jade_pendant   吊坠 / 挂件
4  jade_ring      戒指
5  jade_plaque    牌子 / 无事牌
6  pingan_kou     平安扣
7  guanyin        观音题材
8  buddha         佛公题材
9  ruyi           如意题材
10 leaf           叶子题材
11 landscape      山水题材
12 pixiu          貔貅题材
13 gourd          葫芦题材
```

颜色和种水不强行靠 YOLO 分类，仍由图像颜色特征、透明度/纹理启发式和主播讲解文本共同判断。YOLO 主要负责样式、题材、主体区域。

## 标注格式

每张图片一个同名 `.txt` 标签文件，使用 YOLO 检测格式：

```text
class_id center_x center_y width height
```

坐标全部是 0 到 1 的归一化比例。

## 从人工校正反馈生成弱标注

前端“样图多模态分析”里提交人工校正后，后端会把记录追加到：

```text
data/jade_feedback.jsonl
```

用下面命令把这些反馈样本转成 YOLO 数据集：

```powershell
python scripts\build_jade_yolo_dataset_from_feedback.py --write-yaml
```

说明：

- 只使用人工校正里的“样式”和“题材”生成 YOLO 类别。
- 如果反馈里没有检测框，前期会使用整图框作为弱标注。
- 每 5 条样本默认放 1 条到 `val`，其余放到 `train`。
- 这个弱标注模型能先跑起来，但精度不会等同于人工框选后的精标模型。

## 训练小模型

```powershell
python scripts\train_jade_yolo.py --data data\jade_yolo\dataset.yaml --model yolo11n.pt --epochs 50
```

训练完成后脚本会把最优权重复制到：

```text
models/jade-yolo.pt
```

实时识别默认会读取这个文件。服务器上如需启用 YOLO 推理，需要安装 `ultralytics` 并配置 `JLAO_YOLO_MODEL`。

## 单张样图测试

```powershell
python scripts\analyze_jade_sample.py --image tmp\sample.jpg --text "这件白冰冰种观音，高 45mm，宽 28mm" --pretty
```

这个命令会输出 JSON，包含颜色、种水、样式、题材、尺寸、价格、置信度、图像证据、文字证据和底层识别信号。
