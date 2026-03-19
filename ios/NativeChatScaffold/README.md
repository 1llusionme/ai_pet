# NativeChatScaffold

这个目录提供 iOS 原生聊天主链路的可复用骨架代码，可直接复制到 Xcode 的 SwiftUI 工程中。

## 包含内容

- `ChatModels.swift`：消息模型与状态定义
- `ChatAPI.swift`：健康检查、历史消息、流式聊天请求
- `ChatViewModel.swift`：会话状态与交互逻辑
- `NativeChatView.swift`：原生聊天界面

## 接入步骤

1. 在 Xcode 创建 SwiftUI App 工程。
2. 将本目录四个 `.swift` 文件拖入工程。
3. 在 `ChatAPI(baseURL:)` 中传入后端域名。
4. 在应用入口将首页设置为 `NativeChatView`。

## 依赖

- iOS 16+
- Swift 5.9+
