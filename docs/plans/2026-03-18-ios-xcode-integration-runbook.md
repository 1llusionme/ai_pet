# iOS 混合壳接入与联调手册（执行版）

## 1. 目标

- 把原生聊天主链路接入 iOS App 首页。
- 把非核心能力放在 WebView 页签中继续可用。
- 完成首轮真机联调，形成可进入 TestFlight 的基础包。
- 零基础操作请先看：`docs/plans/2026-03-18-xcode-零基础操作指南.md`

## 2. 代码目录

- 原生聊天骨架：`ios/NativeChatScaffold`
- 混合壳骨架：`ios/HybridAppScaffold`
- XcodeGen 模板：`ios/HybridAppScaffold/project.yml`

## 3.1 快速生成工程（可选）

1. 安装 XcodeGen。
2. 进入 `ios/HybridAppScaffold` 目录执行 `xcodegen generate`。
3. 打开生成的 `MindShadowHybrid.xcodeproj`。
4. 在 `Signing & Capabilities` 配置团队签名。

## 3.2 Xcode 接入步骤

1. 新建 SwiftUI App 工程（iOS 16+）。
2. 把 `ios/NativeChatScaffold` 下文件拖入项目并勾选目标。
3. 把 `ios/HybridAppScaffold` 下文件拖入项目并勾选目标。
4. 删除工程默认 `@main` 入口，保留 `MindShadowHybridApp` 作为入口。
5. 在 `MindShadowHybridApp.swift` 中替换：
   - `apiBaseURL` 为你的后端生产或测试域名。
   - `webBaseURL` 为你的 Web 站点域名。
6. 在 `Signing & Capabilities` 配置团队签名，确保真机可运行。

## 4. 必做配置

- `Info.plist` 中确保 ATS 策略满足你的域名策略，优先全 HTTPS。
- 若 Web 页涉及登录态，统一 Cookie 域名与 SameSite 策略。
- 服务端开放：
  - `GET /api/health`
  - `GET /api/history`
  - `POST /api/chat/stream`

## 5. 联调清单

### 聊天主链路

- 启动后进入聊天页，显示欢迎语。
- 发送问题后消息立即入列表。
- AI 回复流式刷新，结束后变为稳定消息。
- 断网时出现错误提示，再次联网可重试成功。
- 点击“新对话”后历史消息不串台。

### 混合页签

- 资产页正常加载，不白屏。
- 设置页正常加载，不闪退。
- 切回聊天页时状态不丢失。

## 6. 冒烟验收口径

- 连续发送 20 条消息，失败不超过 1 条。
- 首次进入聊天可交互时间小于 2.5 秒。
- WebView 三次来回切换无明显卡顿。

## 7. 提审前最小动作

- 固化构建环境：Release 配置、版本号、Build 号。
- 替换正式图标与应用名。
- 准备 TestFlight 说明：本次新增原生聊天主链路与已知限制。
