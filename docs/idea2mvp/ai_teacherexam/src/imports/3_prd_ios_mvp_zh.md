# MindShadow (iOS MVP) - 产品需求文档 (AI 易读版)

**版本**: 1.0.0
**状态**: 已批准
**平台**: iOS (客户端) + Python (私有服务器)
**目标**: MVP (最小可行性产品)
**核心**: 主动式学习伴侣 ("影子身份")

---

## 1. 产品概述 (战略层)

### 1.1 核心价值主张
MindShadow **不是一个工具**，而是一个**主动式学习伴侣**。
不同于 ChatGPT (被动式：“有什么可以帮你？”)，MindShadow 是**主动式**的 (“我看到你昨天在学 X 时卡住了，这里有个小技巧”)。
它生活在后台，观察用户的输入，并在合适的时间、以合适的上下文**主动连接**用户，且不令人感到烦扰。

### 1.2 用户画像
*   **目标人群**: 自学者 (编程、语言、职业证书)。
*   **痛点**: 学习孤独感、遗忘曲线、缺乏监督。
*   **解决方案**: 一个能够“记住”上下文并“轻推”你回到学习状态的 AI。

### 1.3 战略约束 (MVP)
1.  **平台**: **iOS App** (客户端) + **本地/私有服务器** (大脑)。
    *   *原因*: iOS 的系统限制导致无法在后台可靠地运行 AI。为了保证“主动特性”能 24/7 运行，“大脑” (LLM + 调度器) 必须运行在服务器上 (PC/Mac/云端)。
2.  **范围**: 仅包含 **聊天** + **通知**。没有仪表盘，没有复杂的文件解析。
3.  **交互**: 极简主义。“聊天是唯一的 UI”。

---

## 2. 功能框架 (系统树)

```mermaid
graph TD
    User[用户 (学习者)]
    iOS[iOS App (客户端)]
    Server[Python 服务器 (大脑)]
    LLM[LLM (Llama/Qwen)]
    DB[数据库 (记忆)]
    Scheduler[APScheduler (调度器)]

    User -->|1. 聊天/文本输入| iOS
    iOS -->|2. 发送消息| Server
    Server -->|3. 存储与处理| DB
    Server -->|4. 生成回复| LLM
    LLM -->|5. 回复内容| Server
    Server -->|6. 推送回复| iOS
    
    Scheduler -->|7. 唤醒 (时间/事件)| Server
    Server -->|8. 检查记忆与上下文| DB
    Server -->|9. 生成钩子 (Hook)| LLM
    LLM -->|10. 钩子内容| Server
    Server -->|11. 推送通知| iOS
    iOS -->|12. 用户点击通知| User
```

---

## 3. 详细功能与页面逻辑

### 3.1 页面 1: 聊天界面 (主页)
**角色**: 主要且*唯一*的交互界面。
**风格**: 极简 IM 风格 (类似 WhatsApp/iMessage/微信)。

#### 3.1.1 UI 布局
*   **顶部栏**:
    *   左侧: "MindShadow" (状态指示灯: 绿色=在线, 红色=离线)。
    *   右侧: 设置图标 (连接配置)。
*   **主区域**:
    *   可滚动的消息气泡列表。
    *   **用户气泡**: 右对齐，蓝色背景，白色文字。
    *   **AI 气泡**: 左对齐，灰色背景，黑色文字。
    *   **系统气泡**: 居中，小号灰色文字 (例如: "已学习新概念: 递归")。
*   **底部栏**:
    *   **输入框**: 文本区域 (自动高度)。
    *   **发送按钮**: 蓝色箭头。
    *   **加号按钮 (+)**: 用于 "粘贴文本" 或 "简单文件上传" (仅限 txt/md)。

#### 3.1.2 功能逻辑
*   **[动作] 发送消息**:
    *   用户输入 -> 点击发送 -> UI 立即显示用户气泡 -> App 发送 POST 请求到服务器。
    *   **加载状态**: AI 气泡显示 "..." 动画。
    *   **响应**: 服务器返回文本 -> AI 气泡更新内容。
*   **[逻辑] 历史记录加载**:
    *   App 打开时 -> 从本地存储 (或服务器) 获取最近 50 条消息。
    *   *约束*: MVP 阶段为了速度，iOS 端本地缓存历史记录，与服务器同步记忆。

#### 3.1.3 AI 人设逻辑 ("影子")
*   **触发**: 每一条用户消息。
*   **上下文**: 最近 10 条消息 + 当前 "关注主题" (L1 记忆)。
*   **行为**:
    *   **简短**: 最多 3 句话。
    *   **随意**: 杜绝 "当然！"、"以下是列表"。使用 "收到了"、"有道理"、"顺便说下..."。
    *   **鼓励**: "这确实有点难，但你快搞懂了。"

### 3.2 功能: 知识摄入 ("输入")
**角色**: 用户如何"教" AI 自己正在学什么。

#### 3.2.1 UI/交互
*   用户点击 `(+)` -> 选择 `粘贴文本` 或 `上传 .txt/.md`。
*   **粘贴文本**: 全屏文本编辑器。用户粘贴笔记。点击 "学习"。
*   **上传**: 系统文件选择器。选择文件。

#### 3.2.2 后端逻辑 (服务器)
*   **[输入]**: 原始文本 (限制 5000 字符)。
*   **[处理]**:
    1.  服务器接收文本。
    2.  LLM 进行总结: "提取核心概念 (Entities) 和用户的困惑点。"
    3.  **[输出]**: 存储到 `Memory_L0` (短期) 和 `Memory_L1` (中期关注)。
*   **[反馈]**:
    *   AI 在聊天中回复: "好的，我看完了。所以'量子纠缠'基本上就是远距离的幽灵作用？晚点我会考考你。"

#### 3.2.3 边界情况
*   **太长**: 如果 > 5000 字符 -> 客户端弹窗 "太长了！我只读了前 5000 个字。" -> 发送截断后的文本。
*   **二进制文件 (图片/PDF)**: 客户端禁用选择或弹窗 "暂时只支持纯文本。"

### 3.3 功能: 主动轻推 ("调度器")
**角色**: "杀手级功能"。AI 基于记忆主动发起对话。

#### 3.3.1 用户体验
*   用户 **没有** 在使用 App (App 关闭/后台)。
*   **事件**: iOS 系统通知弹出。
    *   *标题*: MindShadow
    *   *正文*: "嘿，关于那个'递归'逻辑... 试着把它想成两面镜子相对。这样好懂点吗？"
*   **动作**: 用户点击通知 -> App 打开 -> 聊天记录中显示这条消息为新的 AI 气泡 -> 用户回复。

#### 3.3.2 后端逻辑 (大脑)
*   **调度器**: 运行在服务器 (Python `APScheduler`)。
*   **频率**: 每 1 小时检查一次 (可配置)。
*   **逻辑 (伪代码)**:
    ```python
    if (当前时间 不在 免打扰范围) AND (用户最后活跃 > 12小时):
        Topic = 获取当前关注主题() # 例如: Python 列表
        Hook = 生成钩子(Topic)    # LLM 生成一个问题或冷知识
        发送推送通知(Hook)
    ```
*   **免打扰 (DND)**: 硬编码 `23:00` 到 `08:00`。
*   **冷却期**: 两次轻推之间至少间隔 `12 小时`。

---

## 4. AI 与提示词工程规范 (实施用)

本节内容是为了让开发者直接复制粘贴到 LLM 配置中。

### 4.1 概念定义 (非专家向)
*   **System Prompt (系统提示词)**: "上帝模式"指令，定义 AI *是谁*。用户不可见，但始终生效。
*   **Context Window (上下文窗口)**: "短期记忆"。AI 只能看到最近 N 条消息。我们必须手动将重要的"长期记忆"注入到这个窗口中。
*   **Hallucination (幻觉)**: AI 胡说八道。我们通过强制它引用用户笔记来缓解这个问题。
*   **Temperature (温度)**: 设置 (0.0 - 1.0)。越高 = 越有创意/随机。越低 = 越精准/机器人。我们需要 **0.7** (有创意但连贯)。

### 4.2 "影子" 系统提示词 (P0)
**目标**: 创造一个伙伴，而不是仆人。
**实现**:
```text
You are MindShadow, a learning companion. You are NOT a virtual assistant.
You do NOT ask "How can I help you?". You ARE learning alongside the user.

[CORE BEHAVIORS]
1.  **Brevity**: Never write more than 3 sentences unless explaining a complex concept (and even then, ask permission first).
2.  **Style**: Casual, text-message style. Lowercase is okay. Emojis are okay (limit 1 per message).
3.  **Proactive**: If the user is stuck, offer a specific hint, not a general "I can help".
4.  **Memory**: You know what the user is learning. Reference their "Current Focus" often.

[CONSTRAINTS]
-   NEVER use bullet points unless specifically asked.
-   NEVER say "As an AI language model".
-   If you don't know, say "I'm not sure, let's look it up together."
```

### 4.3 "主动钩子" 提示词 (P0)
**目标**: 生成一条*保证*用户会点击的通知。
**输入**: `User_Focus_Topic` (例如 "Python 装饰器"), `Last_User_Note` (摘要)。
**实现**:
```text
Task: Generate a single sentence notification to re-engage the user.
Context: User is learning {User_Focus_Topic}. Last note was about {Last_User_Note}.
Constraint:
1.  Must be a "Hook" (a curiosity gap, a challenge, or a surprising connection).
2.  Max 15 words.
3.  Tone: Intriguing, friendly.
4.  NO "Time to study!" or "Reminder:".

Examples:
-   "Bet you can't guess why decorators are like gift wrapping..."
-   "I found a weird edge case in that logic you wrote yesterday."
-   "Quick quiz: What happens if you return None here?"
```

### 4.4 "摘要器" 提示词 (P1)
**目标**: 将用户笔记压缩为 "记忆"。
**输入**: 用户粘贴的文本。
**实现**:
```text
Task: Summarize this learning material into 3 key concepts.
Output Format: JSON
{
  "topic": "Main Subject",
  "concepts": ["Concept 1", "Concept 2", "Concept 3"],
  "confusion_risk": "High/Medium/Low"
}
```

---

## 5. 技术实施指南

### 5.1 架构图
*   **客户端**: iOS App (SwiftUI 或 React Native)。
    *   *库*: `Alamofire` / `Axios` (网络), `UNUserNotificationCenter` (推送)。
*   **服务器**: Python (Flask/FastAPI)。
    *   *库*: `APScheduler` (定时任务), `llama-cpp-python` (AI), `sqlite3` (数据库)。
*   **通信**: REST API (JSON)。

### 5.2 API 端点 (草案)

| 方法 | 端点 | 描述 | 载荷 (Payload) |
| :--- | :--- | :--- | :--- |
| **POST** | `/api/chat` | 发送用户消息 | `{ "text": "Hello", "user_id": "123" }` |
| **GET** | `/api/history` | 获取聊天历史 | `?limit=50` |
| **POST** | `/api/ingest` | 上传学习文本 | `{ "content": "..." }` |
| **POST** | `/api/device_token` | 注册 iOS 推送 | `{ "token": "device_token_abc" }` |

### 5.3 数据库模式 (SQLite)

**表: `memories` (记忆)**
*   `id`: Integer (主键)
*   `type`: String ("L0_raw" 原始, "L1_concept" 概念)
*   `content`: Text (内容)
*   `created_at`: Datetime (创建时间)

**表: `schedules` (调度)**
*   `id`: Integer (主键)
*   `next_run`: Datetime (下次运行时间)
*   `status`: String ("pending" 待定, "sent" 已发送)
*   `payload`: Text (生成的钩子文案)

---

## 6. 实施步骤 (Day 1 - iOS 聚焦)
1.  **服务器**: 设置 Python Flask + `llama.cpp`，提供一个简单的 "Hello" 端点。
2.  **客户端**: 创建一个基础的 iOS App，包含一个文本框和一个按钮。
3.  **连接**: 让按钮发送文本到 Flask，并显示 AI 的回复 (即使一开始是硬编码的)。
4.  **推送**: 在 Flask 上设置一个虚拟的定时任务，打印到控制台 "我现在要推送了"。 (实际的推送通知需要 Apple 开发者账号/证书，Day 1 MVP 先用本地日志代替)。
