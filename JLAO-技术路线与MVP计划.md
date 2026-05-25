# JLAO 技术路线与 MVP 计划

日期：2026-05-05
版本：v0.1
项目：Jade Live AI Optimizer（JLAO）
中文名称：翡翠直播间实时 AI 优化系统
硬性目标：一个月内完成可演示 MVP Demo

## 1. 技术路线结论

第一版采用：

```text
前端：Vue 3 + Vite + TypeScript
后端：Python + FastAPI
实时通信：WebSocket
数据库：PostgreSQL，MVP 早期也可先用 SQLite
缓存/队列：Redis，MVP 早期可先不引入
AI：大模型 API + 中文角色提示词
音频：先模拟文本流，再接录音转写，最后接实时转写
视频：FFmpeg + OpenCV，先预留结构，再做抽帧、裁剪、画面预处理
```

核心判断：

- 项目本质是实时中控台，不是 SEO 网站。
- AI、音频、视频处理更适合放在 Python 后端。
- 一个月 demo 要先证明业务价值，不要被复杂采集、OCR、多设备拖住。
- OpenCV 明确进入技术栈，但第一周不作为核心阻塞项。

## 2. MVP 核心闭环

一个月内必须跑通：

```text
创建直播
-> 选择当前翡翠商品
-> 输入或转写直播内容
-> AI 生成建议
-> 运营人工审核
-> 复制或标记使用
-> 直播结束生成复盘
```

只要这个闭环跑通，JLAO 的价值就可以演示。

## 3. 总体架构

```text
直播文本 / 录音转写 / 模拟文本流
        |
        v
实时上下文引擎
        |
        +--> 当前商品资料
        +--> 最近直播内容
        +--> 运营反馈记录
        |
        v
AI 建议生成服务
        |
        +--> 商品讲解建议
        +--> 漏讲提醒
        +--> 场控互动建议
        +--> 用户答疑建议
        +--> 合规风险检查
        |
        v
Web 中控台
        |
        v
人工审核 / 编辑 / 复制 / 使用 / 反馈
        |
        v
复盘报告
```

## 4. 前端技术方案

### 4.1 技术栈

```text
Vue 3
Vite
TypeScript
Pinia
Vue Router
Naive UI 或 Element Plus
ECharts
WebSocket
Axios
```

### 4.2 页面

MVP 只做 3 个页面：

```text
1. 登录页
2. 直播中控台
3. 商品库
4. 复盘报告
```

### 4.2.1 UI 风格

JLAO 前端风格定位为直播中控大屏：

```text
深色背景
高对比状态
高信息密度
实时数据优先
建议卡片可快速操作
风险提醒醒目
顶部显示登录用户和角色
```

第一版不做营销感页面，不做普通白底表单后台。

### 4.3 直播中控台布局

```text
顶部：直播状态、当前商品、AI 状态、开始/结束按钮

左侧：实时转写
中间：AI 建议卡片
右侧：商品资料、漏讲提醒、风险提醒
底部：建议日志、简单数据、复盘入口
```

### 4.4 前端组件拆分

```text
LiveDashboard.vue          直播中控主页面
TranscriptPanel.vue        实时转写面板
SuggestionPanel.vue        AI 建议列表
SuggestionCard.vue         AI 建议卡片
ProductCard.vue            当前商品卡
RiskPanel.vue              风险提醒面板
SessionStatusBar.vue       直播状态栏
ProductLibrary.vue         商品库页面
ReplayReport.vue           复盘报告页面
```

### 4.5 前端状态

Pinia store：

```text
useSessionStore            当前直播状态
useProductStore            商品数据
useTranscriptStore         实时转写
useSuggestionStore         AI 建议
useReplayStore             复盘报告
useAuthStore               登录状态和用户角色
```

## 5. 后端技术方案

### 5.1 技术栈

```text
Python
FastAPI
Pydantic
SQLAlchemy 或 SQLModel
WebSocket
PostgreSQL 或 SQLite
FFmpeg
OpenCV
Pillow
```

### 5.2 后端模块

```text
app/main.py                         FastAPI 入口
app/api/sessions.py                 直播会话接口
app/api/products.py                 商品接口
app/api/suggestions.py              建议接口
app/api/replay.py                   复盘接口
app/ws/session_ws.py                WebSocket 推送
app/models/                         数据模型
app/schemas/                        Pydantic Schema
app/services/transcript_service.py  转写/模拟文本服务
app/services/context_service.py     上下文服务
app/services/agent_service.py       AI 建议服务
app/services/compliance_service.py  合规检查服务
app/services/replay_service.py      复盘服务
app/services/frame_service.py       画面抽帧和 OpenCV 预处理
```

## 6. 视频处理技术路线

### 6.1 技术栈

```text
FFmpeg
OpenCV
Pillow
OCR 引擎，后续可选
多模态大模型，后续可选
```

### 6.2 OpenCV 在 JLAO 中的定位

OpenCV 用于直播画面理解前的本地预处理。

主要用途：

```text
直播窗口截图
每 2-5 秒抽帧
裁剪商品展示区
裁剪数据大屏区
检测画面是否变化
检测画面是否模糊
检测亮度和曝光
OCR 前图像增强
多模态模型前图像压缩和标准化
```

OpenCV 不负责生成直播建议，建议仍由 AI 根据上下文生成。

### 6.3 MVP 阶段视频优先级

```text
P0：先跑通直播文本 + 商品资料 + AI 建议
P1：预留 FrameSnapshot 数据结构和接口
P2：支持手动上传截图，让 AI 分析画面
P3：接入 OpenCV 自动抽帧和基础图像检测
P4：接入 OCR 和多模态画面理解
```

### 6.4 FrameSnapshot 数据结构

```text
id
session_id
timestamp
image_path
summary
detected_scene
sharpness_score
brightness_score
change_score
created_at
```

### 6.5 第一个月内的实际目标

一个月 Demo 内，OpenCV 的目标不是做完整视觉识别，而是证明系统具备画面接入能力：

```text
可以上传或抽取一张直播截图
-> OpenCV 做基础预处理
-> 保存为 FrameSnapshot
-> 后续进入上下文
```

复杂商品识别、数据大屏 OCR、证书 OCR 放到 Demo 后继续做。

## 7. AI 服务路线

### 7.1 MVP 原则

第一版不做模型训练，不做 fine-tune。

先使用：

```text
结构化商品资料
+ 最近直播文本
+ 中文角色提示词
+ 合规规则
= AI 建议
```

### 7.2 Agent 划分

MVP 做 5 个 AI 角色：

```text
商品讲解建议
专业漏讲提醒
场控互动建议
用户答疑建议
合规风险检查
```

复盘 Agent 第 4 周加入。

### 7.3 建议生成频率

MVP 建议：

```text
每 10-20 秒生成一次普通建议
出现风险词立即生成风险提醒
用户问题出现时优先生成答疑建议
同类型建议至少间隔 20 秒
界面只展示最高优先级 3-5 条
```

### 7.4 输出格式

AI 输出统一结构：

```json
{
  "type": "主播话术",
  "priority": 2,
  "risk_level": "低",
  "target_role": "主播",
  "content": "这只可以补一下圈口和自然光效果，直播灯光下会显得更亮一点。",
  "reason": "主播刚讲了颜色，但还没有说明圈口和光线差异。",
  "related_product": "冰飘花手镯",
  "suggested_timing": "现在"
}
```

## 8. 数据库设计

MVP 核心表：

```text
live_sessions
products
transcript_segments
suggestions
suggestion_feedback
replay_reports
script_assets
frame_snapshots
```

### 8.1 live_sessions

```text
id
title
platform
anchor_name
operator_name
status
start_time
end_time
notes
created_at
updated_at
```

### 8.2 products

```text
id
name
category
material
color
water
size
weight
certificate
flaws
cautions
price
selling_points
faq
recommended_scripts
created_at
updated_at
```

### 8.3 transcript_segments

```text
id
session_id
start_time
end_time
text
keywords
summary
created_at
```

### 8.4 suggestions

```text
id
session_id
product_id
type
target_role
priority
risk_level
content
reason
source_context
status
created_at
updated_at
```

### 8.5 suggestion_feedback

```text
id
suggestion_id
action
edited_content
feedback_note
created_at
```

### 8.6 replay_reports

```text
id
session_id
summary
useful_scripts
missed_points
risk_warnings
audience_questions
next_suggestions
created_at
```

### 8.7 frame_snapshots

```text
id
session_id
timestamp
image_path
summary
detected_scene
sharpness_score
brightness_score
change_score
created_at
```

## 9. API 设计

### 9.1 登录

```text
POST /api/auth/login
```

MVP 返回：

```text
token
user
role
```

### 9.2 直播会话

```text
POST /api/sessions
GET /api/sessions
GET /api/sessions/{id}
POST /api/sessions/{id}/start
POST /api/sessions/{id}/stop
```

### 9.3 商品

```text
POST /api/products
GET /api/products
GET /api/products/{id}
PUT /api/products/{id}
DELETE /api/products/{id}
```

### 9.4 转写

```text
POST /api/sessions/{id}/transcript/mock/start
POST /api/sessions/{id}/transcript/manual
GET /api/sessions/{id}/transcripts
```

### 9.5 建议

```text
GET /api/sessions/{id}/suggestions
POST /api/suggestions/{id}/accept
POST /api/suggestions/{id}/edit
POST /api/suggestions/{id}/reject
POST /api/suggestions/{id}/used
POST /api/suggestions/{id}/feedback
```

### 9.6 复盘

```text
POST /api/sessions/{id}/replay
GET /api/sessions/{id}/report
```

### 9.7 画面截图

```text
POST /api/sessions/{id}/frames/upload
GET /api/sessions/{id}/frames
GET /api/frames/{frame_id}
```

### 9.8 WebSocket

```text
ws://localhost:8000/ws/sessions/{session_id}
```

事件：

```text
session_status
transcript_segment
suggestion_created
suggestion_updated
risk_warning
replay_ready
```

## 10. 一个月开发计划

### 第 1 周：项目骨架和模拟直播流

目标：

```text
前端能打开
后端能启动
能创建直播
能选择商品
能显示模拟转写
WebSocket 能推送
```

任务：

```text
创建前端项目
创建后端项目
创建基础页面
创建基础接口
创建商品样例
创建模拟直播文本
实现 WebSocket 推送
```

验收：

```text
打开中控台
点击开始直播
左侧实时出现模拟直播文本
右侧显示当前翡翠商品
```

### 第 2 周：AI 建议生成

目标：

```text
能根据商品和直播文本生成建议
能显示建议卡片
能审核建议
```

任务：

```text
商品讲解建议
专业漏讲提醒
合规检查
建议卡片
接受/编辑/复制/拒绝/已使用
```

验收：

```text
主播讲到颜色时，AI 能提醒补尺寸、证书或自然光效果。
出现高风险话术时，AI 能提示改写。
```

### 第 3 周：答疑、互动和真实转写原型

目标：

```text
建议更像真实场控
能处理用户问题
至少接入一种半真实转写方式
```

任务：

```text
用户答疑建议
场控互动建议
简单成交节奏建议
录音文件转写
OpenCV 截图上传或图片预处理原型
上下文时间线
```

验收：

```text
用户问有裂吗、能便宜吗、自然光会不会灰时，AI 能给出可用回答。
```

### 第 4 周：复盘和 Demo 打磨

目标：

```text
完整演示一场直播
能生成复盘报告
Demo 稳定
```

任务：

```text
复盘报告
Demo 数据
UI 打磨
提示词调优
减少重复建议
修复阻塞问题
准备演示脚本
```

验收：

```text
10 分钟内完成完整 Demo：
创建直播 -> 选择商品 -> 转写输入 -> AI 建议 -> 人工审核 -> 生成复盘
```

## 11. 延后功能

一个月 demo 前不做：

```text
多直播间
多手机轻 Agent
稳定截图识别，但不延后 OpenCV 基础预处理
数据大屏 OCR
官方平台 API
复杂权限
模型 fine-tune
LangGraph 复杂流程
向量库高级检索
生产级部署
```

这些功能有价值，但不能影响 MVP。

## 12. Demo 必备样例数据

### 12.1 商品样例

至少准备 10 个：

```text
冰飘花手镯
晴水手镯
阳绿蛋面
紫罗兰挂件
黄翡小佛公
蓝水珠串
糯冰平安扣
春彩手镯
油青雕件
冰种如意
```

### 12.2 用户问题样例

至少准备 30 条：

```text
有证书吗？
是 A 货吗？
有裂吗？
有纹吗？
自然光会不会灰？
上手显不显黑？
适合多大年龄？
圈口是多少？
厚度多少？
还能便宜吗？
今天能发货吗？
可以退换吗？
这个会不会太薄？
颜色实物会更深吗？
和刚才那只比哪个好？
```

### 12.3 风险话术样例

至少准备 20 条：

```text
这件以后肯定升值
买到就是赚到
全网最低
绝对无瑕
错过再也没有
戴了能转运
保证收藏价值
这个价格不可能再有
```

## 13. 工程节奏建议

开发原则：

```text
先模拟，后真实
先闭环，后精度
先单直播间，后多直播间
先人工审核，后自动辅助
先中文体验，后技术扩展
```

每天结束前都要能回答：

```text
今天是否让 Demo 更完整？
今天是否减少了一个核心风险？
今天是否离一个月 MVP 更近？
```
