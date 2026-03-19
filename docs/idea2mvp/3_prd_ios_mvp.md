# MindShadow (iOS MVP) - Product Requirements Document (AI-Optimized)

**Version**: 1.0.0
**Status**: APPROVED
**Platform**: iOS (Client) + Python (Private Server)
**Target**: MVP (Minimum Viable Product)
**Focus**: Proactive Learning Companion ("Shadow Identity")

---

## 1. Product Overview (Strategic Layer)

### 1.1 Core Value Proposition
MindShadow is **not a tool**; it is a **Proactive Learning Companion**.
Unlike ChatGPT (Passive: "Ask me anything"), MindShadow is **Active** ("I saw you struggling with X yesterday, here's a trick").
It lives in the background, observes user inputs, and **proactively engages** the user at the right time with the right context, without being annoying.

### 1.2 User Persona
*   **Target**: Self-learners (Coding, Language, Professional Certs).
*   **Pain Point**: Loneliness in learning, forgetting curve, lack of accountability.
*   **Solution**: An AI that "remembers" context and "nudges" you back to learning.

### 1.3 Strategic Constraints (MVP)
1.  **Platform**: **iOS App** (Client) + **Local/Private Server** (Brain).
    *   *Why*: iOS constraints prevent reliable background AI processing. The "Brain" (LLM + Scheduler) must run on a server (PC/Mac/Cloud) to ensure the "Proactive" feature works 24/7.
2.  **Scope**: **Chat** + **Notification** ONLY. No Dashboard, no complex file parsing.
3.  **Interaction**: Minimalist. "Chat is the only UI".

---

## 2. Functional Framework (The Tree)

```mermaid
graph TD
    User[User (Learner)]
    iOS[iOS App (Client)]
    Server[Python Server (Brain)]
    LLM[LLM (Llama/Qwen)]
    DB[Database (Memory)]
    Scheduler[APScheduler]

    User -->|1. Chat/Text Input| iOS
    iOS -->|2. Send Message| Server
    Server -->|3. Store & Process| DB
    Server -->|4. Generate Reply| LLM
    LLM -->|5. Reply Content| Server
    Server -->|6. Push Reply| iOS
    
    Scheduler -->|7. Wake Up (Time/Event)| Server
    Server -->|8. Check Memory & Context| DB
    Server -->|9. Generate Nudge (Hook)| LLM
    LLM -->|10. Nudge Content| Server
    Server -->|11. Push Notification| iOS
    iOS -->|12. User Clicks Notification| User
```

---

## 3. Detailed Features & Page Logic

### 3.1 Page 1: The Chat Interface (Home)
**Role**: The primary and *only* interface for interaction.
**Style**: Minimalist IM (WhatsApp/iMessage/WeChat style).

#### 3.1.1 UI Layout
*   **Top Bar**:
    *   Left: "MindShadow" (Status Indicator: Green=Online, Red=Offline).
    *   Right: Settings Icon (Connection Config).
*   **Main Area**:
    *   Scrollable list of message bubbles.
    *   **User Bubble**: Right-aligned, Blue bg, White text.
    *   **AI Bubble**: Left-aligned, Gray bg, Black text.
    *   **System Bubble**: Center, Small Gray text (e.g., "Learned new concept: Recursion").
*   **Bottom Bar**:
    *   **Input Field**: Text area (auto-expand).
    *   **Send Button**: Blue arrow.
    *   **Plus Button (+)**: For "Paste Text" or "Simple File Upload" (txt/md only).

#### 3.1.2 Functional Logic
*   **[Action] Send Message**:
    *   User types -> Click Send -> UI shows user bubble immediately -> App sends POST to Server.
    *   **Loading State**: AI bubble appears with "..." animation.
    *   **Response**: Server returns text -> AI bubble updates.
*   **[Logic] History Loading**:
    *   On App Open -> Fetch last 50 messages from Local Storage (or Server).
    *   *Constraint*: MVP stores history locally on iOS for speed, syncs with Server for memory.

#### 3.1.3 AI Persona Logic (The "Shadow")
*   **Trigger**: Every user message.
*   **Context**: Last 10 messages + Current "Focus Topic" (L1 Memory).
*   **Behavior**:
    *   **Short**: Max 3 sentences.
    *   **Casual**: No "Certainly!", "Here is the list". Use "Got it.", "Makes sense.", "Btw...".
    *   **Encouraging**: "That's tricky, but you're getting it."

### 3.2 Feature: Knowledge Ingestion (The "Input")
**Role**: How the user "teaches" the AI what they are learning.

#### 3.2.1 UI/Interaction
*   User clicks `(+)` -> Selects `Paste Text` or `Upload .txt/.md`.
*   **Paste Text**: Full-screen text editor. User pastes notes. Click "Learn".
*   **Upload**: System file picker. Select file.

#### 3.2.2 Backend Logic (Server)
*   **[Input]**: Raw text (limit 5000 chars).
*   **[Process]**:
    1.  Server receives text.
    2.  LLM summarizes: "Extract key concepts (Entities) and user's confusion points."
    3.  **[Output]**: Store in `Memory_L0` (Short-term) and `Memory_L1` (Mid-term Focus).
*   **[Feedback]**:
    *   AI replies in Chat: "Ok, I've read it. So 'Quantum Entanglement' is basically spooky action at a distance? I'll quiz you on this later."

#### 3.2.3 Edge Cases
*   **Too Long**: If > 5000 chars -> Client alerts "Too long! I only read the first 5000 chars." -> Sends truncated text.
*   **Binary File (Image/PDF)**: Client disables selection or alerts "Text only for now."

### 3.3 Feature: Proactive Nudge (The "Scheduler")
**Role**: The "Killer Feature". AI initiates conversation based on memory.

#### 3.3.1 User Experience
*   User is **NOT** using the app (App is closed/background).
*   **Event**: iOS System Notification pops up.
    *   *Title*: MindShadow
    *   *Body*: "Hey, about that 'Recursion' logic... think of it like a mirror facing a mirror. Does that help?"
*   **Action**: User taps Notification -> App opens -> Chat History shows this message as a new AI bubble -> User replies.

#### 3.3.2 Backend Logic (The Brain)
*   **Scheduler**: Runs on Server (Python `APScheduler`).
*   **Frequency**: Checks every 1 hour (configurable).
*   **Logic (Pseudo-code)**:
    ```python
    if (Time_Now is NOT in DND_Range) AND (User_Last_Active > 12_Hours):
        Topic = Get_Current_Focus_Topic() # e.g., Python Lists
        Hook = Generate_Hook(Topic)       # LLM generates a question/fact
        Send_Push_Notification(Hook)
    ```
*   **DND (Do Not Disturb)**: Hardcoded `23:00` to `08:00`.
*   **Cooldown**: Min `12 hours` between nudges.

---

## 4. AI & Prompt Engineering Specs (For Implementation)

This section is written for the developer to copy-paste into the LLM configuration.

### 4.1 Concept Definitions (For Non-Experts)
*   **System Prompt**: The "God Mode" instruction that defines *who* the AI is. It is hidden from the user but always active.
*   **Context Window**: The "Short-term Memory". The AI can only see the last N messages. We must inject important "Long-term Memory" into this window manually.
*   **Hallucination**: The AI making things up. We mitigate this by forcing it to quote the user's notes.
*   **Temperature**: A setting (0.0 - 1.0). Higher = Creative/Random. Lower = Precise/Robot. We want **0.7** (Creative but coherent).

### 4.2 The "Shadow" System Prompt (P0)
**Goal**: Create a companion, not a servant.
**Implementation**:
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

### 4.3 The "Proactive Hook" Prompt (P0)
**Goal**: Generate a notification that *guarantees* a click.
**Input**: `User_Focus_Topic` (e.g., "Python Decorators"), `Last_User_Note` (Summary).
**Implementation**:
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

### 4.4 The "Summarizer" Prompt (P1)
**Goal**: Compress user notes into "Memory".
**Input**: User pasted text.
**Implementation**:
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

## 5. Technical Implementation Guide

### 5.1 Architecture Diagram
*   **Client**: iOS App (SwiftUI or React Native).
    *   *Libs*: `Alamofire` / `Axios` (Networking), `UNUserNotificationCenter` (Push).
*   **Server**: Python (Flask/FastAPI).
    *   *Libs*: `APScheduler` (Cron), `llama-cpp-python` (AI), `sqlite3` (DB).
*   **Communication**: REST API (JSON).

### 5.2 API Endpoints (Draft)

| Method | Endpoint | Description | Payload |
| :--- | :--- | :--- | :--- |
| **POST** | `/api/chat` | Send user message | `{ "text": "Hello", "user_id": "123" }` |
| **GET** | `/api/history` | Get chat history | `?limit=50` |
| **POST** | `/api/ingest` | Upload learning text | `{ "content": "..." }` |
| **POST** | `/api/device_token` | Register iOS for Push | `{ "token": "device_token_abc" }` |

### 5.3 Database Schema (SQLite)

**Table: `memories`**
*   `id`: Integer (PK)
*   `type`: String ("L0_raw", "L1_concept")
*   `content`: Text
*   `created_at`: Datetime

**Table: `schedules`**
*   `id`: Integer (PK)
*   `next_run`: Datetime
*   `status`: String ("pending", "sent")
*   `payload`: Text (The generated hook)

---

## 6. Implementation Steps (Day 1 - iOS Focus)
1.  **Server**: Set up Python Flask + `llama.cpp` serving a simple "Hello" endpoint.
2.  **Client**: Create a basic iOS App with one text field and one button.
3.  **Connect**: Make the button send text to Flask, and display the AI's response (even if hardcoded at first).
4.  **Push**: Set up a dummy scheduled task on Flask that prints to console "I would push now". (Actual Push Notification requires Apple Developer Account/Certificates, use local logging for Day 1 MVP).

