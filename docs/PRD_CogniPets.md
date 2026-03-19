# 产品需求文档 (PRD) - Cogni-Pets (灵犀伙伴)
**Version**: 4.1 (Development Iteration)
**Status**: Approved for Development
**Last Updated**: 2026-03-16
**Author**: Trae (Senior PM)

---

## 1. 文档变更记录 (Revision History)
| 版本 | 日期 | 修改人 | 修改内容 | 备注 |
| :--- | :--- | :--- | :--- | :--- |
| v1.0 | 2026-03-15 | Trae | 初始草案 | 概念验证 |
| v2.0 | 2026-03-15 | Trae | 深度重构 | 增加架构图与状态机逻辑 |
| v3.0 | 2026-03-15 | Trae | 落地性修正 | 针对评审意见修正性能策略、家长端交互与教育逻辑 |
| v4.0 | 2026-03-15 | Trae | **结构化与逻辑补全** | 恢复完整功能结构，补充每个功能模块的详细逻辑、交互细节与异常处理 |
| v4.1 | 2026-03-16 | Trae | **能力扩展（搜索+视觉问答）** | 新增联网搜索、图片识别、拍照上传问答闭环 |

---

## 2. 产品功能架构图 (Functional Architecture)

```mermaid
graph TD
    Root[Cogni-Pets Client] --> Client[Unity 3D Client]
    Root --> Logic[Local Logic Core]
    
    Client --> Mod_Pet[Module A: 3D Pet Interaction]
    Client --> Mod_Study[Module B: Feynman Learning Mode]
    Client --> Mod_Parent[Module C: Parent Dashboard]
    
    Mod_Pet --> Feat_Touch[Touch Interaction]
    Mod_Pet --> Feat_Voice[Voice Chat]
    Mod_Pet --> Feat_State[State Display (Hunger/Mood)]
    
    Mod_Study --> Feat_QnA[Interactive Q&A]
    Mod_Study --> Feat_Vision[Vision Exploration]
    Mod_Study --> Feat_Reward[Reward System]
    
    Mod_Parent --> Feat_QuickAction[Quick Actions]
    Mod_Parent --> Feat_Report[Weekly Report]
    
    Logic --> Eng_State[State Machine Engine]
    Logic --> Eng_LLM[LLM Inference Engine]
    Logic --> Eng_Mem[Memory System (Vector+SQL)]
    Logic --> Eng_Resource[Resource Arbiter]
```

---

## 3. 详细功能需求 (Detailed Functional Requirements)

### 3.1 模块一：核心交互与养成 (Core Interaction & Nurturing)

#### 3.1.1 宠物状态机 (Pet State Machine)
**功能描述**：维护宠物的生命体征，决定宠物的行为模式和交互反馈。

*   **逻辑详述 (Logic Flow)**：
    1.  **初始化**：App 启动时读取 `PetState` 表。若 `LastLoginTime > 12h`，计算离线期间的状态衰减（Hunger -5/h, Mood -2/h）。
    2.  **状态流转**：
        *   `Normal` (Hunger > 30, Mood > 40): 随机播放 Idle 动画（行走、张望）。
        *   `Hungry` (Hunger <= 30): 播放虚弱动画，点击反馈变为“摸肚子”。
        *   `Sick` (Hunger == 0 持续 > 12h): 宠物卧床，无法触发学习模式。
    3.  **恢复机制**：
        *   喂食交互 -> Hunger + 10 -> 若 Hunger > 30 且之前是 Hungry，转为 Normal。
        *   摸头交互 -> Mood + 2 -> 若 Mood > 40 且之前是 Sad，转为 Normal。

*   **交互细节 (UI/UX)**：
    *   **状态栏**：屏幕左上角显示 Hunger (鸡腿图标) 和 Mood (笑脸图标) 进度条。
    *   **低状态提醒**：当 Hunger < 20 时，宠物头顶出现气泡 🍗，并伴有“咕咕”音效。

*   **异常处理 (Edge Cases)**：
    *   **系统时间篡改**：若检测到当前时间 < LastLoginTime，弹出“时空警察”对话框，重置状态为上次存档值，不进行衰减计算。

#### 3.1.2 3D 触摸与语音交互 (Touch & Voice)
**功能描述**：用户通过点击或语音与宠物进行基础互动。

*   **逻辑详述 (Logic Flow)**：
    1.  **触摸 (Touch)**：
        *   检测 Raycast 命中模型部位（头/肚子/脚）。
        *   **头**：播放 `Happy` 动画，Mood + 2。
        *   **肚子**：播放 `Tickle` (挠痒) 动画，Mood + 1。
        *   **脚**：播放 `Jump` 或 `Angry` 动画，Mood 不变。
    2.  **语音 (Voice - Chat)**：
        *   用户长按“麦克风”按钮 -> 开始录音 -> 松开 -> STT -> LLM (Chat Mode) -> TTS。
        *   **资源互斥**：进入语音模式时，后台暂停 Vision 模块。

*   **交互细节 (UI/UX)**：
    *   **麦克风状态**：
        *   Idle: 灰色静止。
        *   Recording: 红色呼吸动效 + 波形跳动。
        *   Thinking: 蓝色旋转 Loading（掩盖 LLM 延迟）。
        *   Speaking: 绿色常亮 + 宠物口型同步。

---

### 3.2 模块二：费曼学习模式 (Feynman Learning Mode)
**核心价值**：通过“教宠物”来巩固知识，解决“被动灌输”效率低的问题。

#### 3.2.1 学习请求触发 (Study Trigger)
**功能描述**：宠物主动发起学习请求，或响应家长指令。

*   **触发逻辑 (Logic Flow)**：
    *   **被动触发 (Passive)**：家长通过 Dashboard 发送 `[练口语]` 卡片 -> 写入 `TaskQueue` -> 宠物下一帧检测到任务 -> 播放“举手”动画 -> 弹出对话气泡：“我的飞船需要单词能量才能起飞，教教我这个单词吧！”
    *   **主动触发 (Active)**：每天 19:00-21:00 (学习时段)，若 App 前台运行且无操作 > 1分钟 -> 宠物主动询问：“今天学校有什么好玩的知识吗？”

#### 3.2.2 教学互动流程 (Teaching Interaction)
**功能描述**：用户解释知识点，AI 扮演“笨学生”进行提问和反馈。

*   **逻辑详述 (Logic Flow)**：
    1.  **User Input**: 用户语音输入解释（如：“苹果是红色的水果”）。
    2.  **LLM Eval**: 调用本地 LLM 进行逻辑校验 (Prompt: "Role: 5-year-old. Input: {text}. Check logic. Is it clear?")。
    3.  **分支判断**:
        *   **Case A (Clear)**: LLM 返回 `Pass` -> 宠物播放 `Cheer` 动画 -> TTS: "哇！原来是这样！我懂了！" -> EXP + 50。
        *   **Case B (Confused)**: LLM 返回 `Confused` -> 宠物播放 `Confused` 动画 -> TTS: "可是...为什么它是红色的呢？" (追问)。
    4.  **Smart Fallback (智能兜底)**:
        *   计数器 `FailCount`。若 Case B 连续触发 2 次 -> 强制转入 Case A。
        *   TTS 话术：“虽然有点难懂，但我相信你！你是最棒的小老师！”（避免挫败感）。

*   **交互细节 (UI/UX)**：
    *   **思考掩盖 (Masking)**：在 LLM 推理期间（3-5秒），宠物必须做“挠头”、“托腮”等思考动作，不能僵死。
    *   **视觉反馈**：屏幕边缘出现金色粒子特效（表示正在传输知识能量）。

#### 3.2.3 现实探索 (Vision Exploration)
**功能描述**：利用摄像头识别现实物体并进行英语教学。

*   **逻辑详述 (Logic Flow)**：
    1.  **开启**：点击“探索镜”按钮 -> 开启 Camera -> 切换 Resource Mode 为 `Vision` (3D 渲染降级)。
    2.  **检测**：每 1 秒截取一帧 (1fps) -> 传入 YOLOv8n 模型。
    3.  **锁定**：连续 2 帧检测到同一物体 (Confidence > 0.6) -> 锁定目标。
    4.  **互动**：
        *   UI 显示物体英文标签 (e.g., "Apple")。
        *   宠物语音：“这是 Apple 吗？它看起来好好吃！”

*   **异常处理**：
    *   **过热保护**：若设备温度 > 40℃ (通过系统 API 或模拟估算)，强制关闭摄像头并提示：“眼睛累了，休息一下吧”。

#### 3.2.4 自主联网搜索 (Autonomous Web Search)
**功能描述**：学习搭子在回答前可主动联网检索，提供可解释、可追溯的知识点说明。

*   **逻辑详述 (Logic Flow)**：
    1.  **触发判定**：当用户问题包含“最新”“为什么”“怎么证明”“资料来源”等信号词，进入 Search 模式。
    2.  **检索执行**：调用搜索接口抓取前 3 条高相关摘要，提取标题、链接、摘要文本。
    3.  **证据融合**：将检索摘要拼接到 LLM 上下文，生成最终回答，并在回答末尾展示来源条目。
    4.  **降级策略**：检索超时或失败时，自动回退到纯 LLM 回答，同时提示“已使用离线知识回答”。

*   **交互细节 (UI/UX)**：
    *   在回复顶部展示“🔎 已联网检索”标签。
    *   来源条目支持点击查看，默认折叠，避免打断主阅读流。

*   **异常处理**：
    *   搜索服务不可达时不阻断聊天主流程，回复中追加温和提示。

#### 3.2.5 拍照提问与图片识别 (Camera Q&A)
**功能描述**：用户可在聊天输入区直接调起相机拍照上传，围绕题目/知识点发起提问。

*   **逻辑详述 (Logic Flow)**：
    1.  **入口**：输入区新增“拍照”入口，支持调用系统相机或相册选择。
    2.  **上传**：客户端压缩图片后上传，服务端返回 `image_id` 与可访问 URL。
    3.  **识别**：服务端调用视觉模型识别图片内容（题目文本、图形结构、关键元素）。
    4.  **问答**：用户输入问题后，系统将“文本问题 + 图片上下文”联合提交模型生成解释。
    5.  **回写**：会话中保留“图片上传成功”和“图片问答结果”两类消息，便于复盘。

*   **交互细节 (UI/UX)**：
    *   上传后显示缩略图卡片与“识别中”状态。
    *   识别完成后可一键追问“给我出一道类似题”。

*   **异常处理**：
    *   图片过大/格式不支持：提示并引导重新拍照。
    *   识别失败：保留已上传图片，允许用户改为文字描述继续提问。

---

### 3.3 模块三：家长控制台 (Parent Dashboard)

#### 3.3.1 快捷指令卡片 (Quick Action Cards)
**功能描述**：家长无需打字，通过点击预设卡片控制宠物行为。

*   **逻辑详述 (Logic Flow)**：
    1.  **展示**：Dashboard 首页展示 4-6 个常用卡片 (`催作业`, `去睡觉`, `练口语`, `求表扬`)。
    2.  **点击**：
        *   家长点击 `[去睡觉]` -> App 生成指令 JSON `{"type": "sleep", "urgent": true}` -> 写入本地 `CommandQueue`。
    3.  **执行**：
        *   宠物端轮询 `CommandQueue` -> 获取指令 -> 播放打哈欠动画 -> TTS: "我好困呀，你也该睡了吧？" -> 强制进入 Sleep Mode。

*   **数据同步**：
    *   采用本地 SQLite 共享或即时通讯机制（若家长端与儿童端分离，则需云端中转；MVP 阶段假设为同一设备的不同模式，通过本地 DB 交换数据）。

---

### 3.4 模块四：系统与技术架构 (System & Technical)

#### 3.4.1 资源互斥调度器 (Resource Arbiter)
**核心目标**：防止 Unity, LLM, Vision 三大高耗能模块并发导致 Crash 或过热。

*   **状态机逻辑**：
    | 模式 (Mode) | 3D 渲染 | LLM 推理 | Vision 检测 | 适用场景 |
    | :--- | :--- | :--- | :--- | :--- |
    | **Idle** | 30fps | OFF | OFF | 待机、普通触摸 |
    | **Listening** | 30fps | OFF | OFF | 录音中 |
    | **Thinking** | **Static/1fps** | **ON** | OFF | 语音转写与回复生成期间 |
    | **Speaking** | 30fps | OFF | OFF | 播放 TTS |
    | **Vision** | **Hidden/UI Only** | OFF | **ON (1fps)** | 摄像头探索模式 |

#### 3.4.2 记忆系统 (Memory System)
**核心目标**：实现“越用越懂你”的个性化体验。

*   **存储结构**：
    1.  **Fact Store (Vector DB)**:
        *   Schema: `{ "embedding": [...], "text": "用户不喜欢吃胡萝卜", "timestamp": 17156234 }`
        *   写入：LLM 从对话中提取事实 -> Embedding -> Insert。
        *   读取：新对话 -> Embedding -> Top-K Search ->作为 Context 输入 LLM。
    2.  **Status Store (SQLite)**:
        *   Table: `user_profile` (`name`, `age`, `level`, `coins`).

---

## 4. 数据字典 (Data Schema)

### 4.1 本地数据库 (SQLite)
```sql
-- 宠物状态表
CREATE TABLE pet_state (
    id INTEGER PRIMARY KEY,
    hunger INTEGER DEFAULT 80,
    mood INTEGER DEFAULT 80,
    exp INTEGER DEFAULT 0,
    last_login_timestamp LONG
);

-- 任务队列 (用于家长指令)
CREATE TABLE command_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    command_type TEXT, -- 'SLEEP', 'STUDY', 'PRAISE'
    payload TEXT,      -- JSON params
    status INTEGER,    -- 0: Pending, 1: Executed
    created_at LONG
);

-- 学习记录
CREATE TABLE study_logs (
    id INTEGER PRIMARY KEY,
    topic TEXT,        -- 'Math', 'English'
    content TEXT,      -- User's explanation
    is_correct BOOLEAN,
    timestamp LONG
);
```

---

## 5. 验收标准 (Acceptance Criteria)
1.  **性能**：在 iPhone 12 / 小米 11 同等机型上，运行 30 分钟不出现过热降频（FPS < 20）。
2.  **交互**：点击“麦克风”到宠物开始“思考”动画，延迟 < 0.5s。
3.  **教育**：Smart Fallback 机制必须生效，连续 2 次答错必须强制通过。
4.  **家长**：点击 Dashboard 卡片后，宠物端必须在 5 秒内（下一次轮询）做出反应。
