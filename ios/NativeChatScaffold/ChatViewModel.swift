import Foundation

@MainActor
final class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var inputText: String = ""
    @Published var isSending: Bool = false
    @Published var errorText: String?
    @Published var isModelReady: Bool = false
    @Published var modeText: String = "连接中"

    private let api: ChatAPI
    private(set) var userId: String
    private(set) var conversationId: String

    init(api: ChatAPI, userId: String = "ios-user", conversationId: String = "default") {
        self.api = api
        self.userId = userId
        self.conversationId = conversationId
    }

    func bootstrap() async {
        await refreshHealth()
        await loadHistory()
        if messages.isEmpty {
            messages = [ChatMessage(id: UUID().uuidString, role: .ai, content: "你好，我在。今天先从哪一块开始？", timestamp: Date())]
        }
    }

    func refreshHealth() async {
        do {
            let health = try await api.fetchHealth()
            let ready = health.llm?.needs_api_key != true && health.llm?.remote_ready != false
            isModelReady = ready
            modeText = ready ? "模型可用" : "降级模式"
        } catch {
            isModelReady = false
            modeText = "离线"
        }
    }

    func loadHistory() async {
        do {
            let loaded = try await api.fetchHistory(userId: userId, conversationId: conversationId)
            messages = loaded.sorted { $0.timestamp < $1.timestamp }
        } catch {
            errorText = error.localizedDescription
        }
    }

    func send() async {
        let trimmed = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty || isSending {
            return
        }
        errorText = nil
        isSending = true
        inputText = ""

        let userMessage = ChatMessage(id: UUID().uuidString, role: .user, content: trimmed, timestamp: Date())
        messages.append(userMessage)

        let typingId = UUID().uuidString
        messages.append(ChatMessage(id: typingId, role: .ai, content: "", timestamp: Date(), isTyping: true))

        do {
            var streamedText = ""
            try await api.streamChat(
                text: trimmed,
                userId: userId,
                conversationId: conversationId,
                onMeta: { [weak self] mode, _ in
                    guard let self else { return }
                    Task { @MainActor in
                        self.modeText = mode == "remote" ? "远程模型" : "降级模式"
                    }
                },
                onDelta: { [weak self] delta in
                    guard let self else { return }
                    streamedText += delta
                    Task { @MainActor in
                        self.updateTypingMessage(id: typingId, content: streamedText)
                    }
                },
                onDone: { [weak self] reply, _ in
                    guard let self else { return }
                    let finalText = reply.isEmpty ? streamedText : reply
                    Task { @MainActor in
                        self.finishTypingMessage(id: typingId, finalContent: finalText)
                    }
                }
            )
        } catch {
            removeTypingMessage(id: typingId)
            errorText = error.localizedDescription
            messages.append(ChatMessage(id: UUID().uuidString, role: .system, content: "发送失败，请重试。", timestamp: Date()))
        }

        isSending = false
    }

    func createNewConversation() {
        conversationId = "c-\(Int(Date().timeIntervalSince1970))-\(Int.random(in: 100...999))"
        messages = [ChatMessage(id: UUID().uuidString, role: .ai, content: "新对话已开始，我们继续。", timestamp: Date())]
    }

    private func updateTypingMessage(id: String, content: String) {
        guard let index = messages.firstIndex(where: { $0.id == id }) else {
            return
        }
        messages[index] = ChatMessage(id: id, role: .ai, content: content, timestamp: messages[index].timestamp, isTyping: true)
    }

    private func finishTypingMessage(id: String, finalContent: String) {
        guard let index = messages.firstIndex(where: { $0.id == id }) else {
            return
        }
        messages[index] = ChatMessage(id: id, role: .ai, content: finalContent, timestamp: messages[index].timestamp, isTyping: false)
    }

    private func removeTypingMessage(id: String) {
        messages.removeAll { $0.id == id }
    }
}
