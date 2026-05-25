# 飞书 Bot 监听配置指南

本文档记录如何在 JLAO 项目中配置飞书 Bot，实现与 Bot 的实时双向对话。

---

## 一、前置条件

1. **lark-cli 已配置**
   ```bash
   lark-cli config show
   ```
   应能看到 `appId`、`brand: feishu` 等信息。

2. **Bot 应用已创建**
   - 在 [飞书开放平台](https://open.feishu.cn/) 创建企业自建应用
   - 记录 `App ID`（如 `cli_aa8d1c10e238dbc4`）
   - 开通以下权限：
     - `im:message:send`（发送消息）
     - `im:message:readonly`（读取消息）
     - `im:chat:readonly`（读取群信息，可选）

3. **发布应用**
   - 在飞书开放平台将应用发布为"已发布"状态
   - 将 Bot 添加到你希望对话的群聊，或在单聊中搜索 Bot 名称

---

## 二、快速验证（Bot 给你发消息）

用 Bot 身份给自己发一条测试消息，验证单向通道：

```bash
lark-cli im +messages-send \
  --as bot \
  --user-id "ou_xxxxxxxxxxxxxxxx" \
  --text "你好，我是你的飞书 CLI 智能体"
```

> `--user-id` 可通过 `lark-cli auth status --verify` 查看自己的 `userOpenId`。

如果飞书收到消息，说明 **Bot 发消息** 通路已通。

---

## 三、双向对话（事件监听）

### 3.1 命令行启动（临时测试）

```bash
lark-cli event consume --as bot im.message.receive_v1
```

这是阻塞命令，运行期间 Bot 会实时监听收到的消息。

> **注意**：AI 子进程环境（如 Claude Code background 模式）会关闭 stdin，导致监听立即退出。需用 `sleep` 管道保持 stdin 打开：
> ```bash
> sleep 999999 | lark-cli event consume --as bot im.message.receive_v1
> ```

### 3.2 收到消息后自动回复

事件监听输出的是 NDJSON 格式，每收到一条消息输出一行 JSON：

```json
{
  "type": "im.message.receive_v1",
  "chat_id": "oc_xxxxxxxx",
  "sender_id": "ou_xxxxxxxx",
  "content": "hello"
}
```

如需自动回复，需额外编写脚本解析 JSON 并调用：

```bash
lark-cli im +messages-send --as bot --chat-id "<chat_id>" --text "收到"
```

---

## 四、持久化运行脚本

项目目录 `scripts/` 下提供了三个脚本，用于长期运行 Bot 监听：

| 脚本 | 作用 | 用法 |
|------|------|------|
| `start-bot-listener.ps1` | 前台运行，实时显示日志 | PowerShell 执行 ` .\scripts\start-bot-listener.ps1` |
| `start-bot-listener-background.vbs` | **后台隐藏运行**，无黑窗口 | **双击运行**，Bot 持续在线 |
| `stop-bot-listener.bat` | 停止后台监听 | 双击运行 |

### 日志位置

```
JLAO/logs/bot-listener.log
```

脚本已内置自动重启逻辑，监听进程崩溃或断线后会在 5 秒后自动重连。

---

## 五、与 AI 结合（进阶）

当前配置已实现：
- [x] Bot 发消息给用户
- [x] Bot 实时接收用户消息

如需让 Bot **智能回复**（如处理自然语言指令、生成文档、查询数据），需要：

1. **消息处理层**：读取 `event consume` 的 JSON 输出
2. **AI 推理层**：将用户消息送入大模型（`bl text chat` 或百炼应用）
3. **回复层**：将 AI 结果通过 `lark-cli im +messages-send` 发回用户

示例流程：

```
用户发消息 → event consume 捕获 → 解析 content
                                    ↓
                              bl text chat "用户说：xxx"
                                    ↓
                              lark-cli im +messages-send 回复结果
```

---

## 六、常见问题

### Q1: 事件监听启动后立即退出

**原因**：stdin 被关闭（常见于 AI agent 子进程）。

**解决**：使用 `sleep` 管道保持 stdin 打开：
```bash
sleep 999999 | lark-cli event consume --as bot im.message.receive_v1
```

### Q2: Bot 收不到消息

- 检查 Bot 是否已添加到聊天会话中
- 检查飞书开放平台是否已开通 `im:message:readonly` 权限
- 检查应用是否已发布（未发布的应用只能在测试企业内使用）

### Q3: 监听断开后不自动重连

使用 `scripts/start-bot-listener.ps1` 或 `.vbs` 启动，已内置循环重启逻辑。

---

## 七、相关命令速查

```bash
# 查看配置
lark-cli config show

# 查看认证状态
lark-cli auth status --verify

# Bot 发消息
lark-cli im +messages-send --as bot --chat-id "<id>" --text "内容"

# 启动事件监听
sleep 999999 | lark-cli event consume --as bot im.message.receive_v1

# 搜索群聊
lark-cli im +chat-search --query "群名称"
```

---

## 八、文件索引

| 文件 | 说明 |
|------|------|
| `scripts/start-bot-listener.ps1` | Bot 监听启动脚本（前台） |
| `scripts/start-bot-listener-background.vbs` | Bot 监听启动脚本（后台隐藏） |
| `scripts/stop-bot-listener.bat` | 停止 Bot 监听 |
| `logs/bot-listener.log` | 运行日志 |
