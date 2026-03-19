import Foundation

enum ChatRole: String, Codable {
    case user
    case ai
    case system
}

struct ChatMessage: Identifiable, Hashable {
    let id: String
    let role: ChatRole
    let content: String
    let timestamp: Date
    var isTyping: Bool = false
}

struct HealthState: Codable {
    struct LLM: Codable {
        let provider: String?
        let remote_ready: Bool?
        let needs_api_key: Bool?
    }

    let status: String?
    let llm: LLM?
}

struct HistoryMessage: Codable {
    let id: String
    let role: String
    let content: String
    let timestamp: String
}

struct HistoryResponse: Codable {
    let messages: [HistoryMessage]
}
