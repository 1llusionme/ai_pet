import Foundation

final class ChatAPI {
    private let baseURL: URL
    private let session: URLSession

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    func fetchHealth() async throws -> HealthState {
        let requestURL = baseURL.appending(path: "/api/health")
        let (data, response) = try await session.data(from: requestURL)
        try validate(response: response, data: data)
        return try JSONDecoder().decode(HealthState.self, from: data)
    }

    func fetchHistory(userId: String, conversationId: String, limit: Int = 50) async throws -> [ChatMessage] {
        var components = URLComponents(url: baseURL.appending(path: "/api/history"), resolvingAgainstBaseURL: false)
        components?.queryItems = [
            URLQueryItem(name: "user_id", value: userId),
            URLQueryItem(name: "conversation_id", value: conversationId),
            URLQueryItem(name: "limit", value: "\(limit)")
        ]
        guard let url = components?.url else {
            throw URLError(.badURL)
        }
        let (data, response) = try await session.data(from: url)
        try validate(response: response, data: data)
        let payload = try JSONDecoder().decode(HistoryResponse.self, from: data)
        return payload.messages.map {
            ChatMessage(
                id: $0.id,
                role: ChatRole(rawValue: $0.role) ?? .system,
                content: $0.content,
                timestamp: ISO8601DateFormatter().date(from: $0.timestamp) ?? Date()
            )
        }
    }

    func streamChat(
        text: String,
        userId: String,
        conversationId: String,
        onMeta: @escaping (_ mode: String?, _ searchUsed: Bool) -> Void,
        onDelta: @escaping (_ delta: String) -> Void,
        onDone: @escaping (_ reply: String, _ mode: String?) -> Void
    ) async throws {
        let requestURL = baseURL.appending(path: "/api/chat/stream")
        var request = URLRequest(url: requestURL)
        request.httpMethod = "POST"
        request.timeoutInterval = 120
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode([
            "text": text,
            "user_id": userId,
            "conversation_id": conversationId
        ])

        let (bytes, response) = try await session.bytes(for: request)
        try validate(response: response, data: Data())

        for try await line in bytes.lines {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty {
                continue
            }
            guard let payloadData = trimmed.data(using: .utf8) else {
                continue
            }
            guard let payload = try? JSONSerialization.jsonObject(with: payloadData) as? [String: Any] else {
                continue
            }
            let type = String(describing: payload["type"] ?? "")
            if type == "meta" {
                let mode = payload["mode"] as? String
                let searchUsed = payload["search_used"] as? Bool ?? false
                onMeta(mode, searchUsed)
                continue
            }
            if type == "delta" {
                let delta = payload["delta"] as? String ?? ""
                if !delta.isEmpty {
                    onDelta(delta)
                }
                continue
            }
            if type == "done" {
                let reply = payload["reply"] as? String ?? ""
                let mode = payload["mode"] as? String
                onDone(reply, mode)
            }
        }
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        guard (200..<300).contains(http.statusCode) else {
            if let payload = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = payload["error"] as? String {
                throw NSError(domain: "ChatAPI", code: http.statusCode, userInfo: [NSLocalizedDescriptionKey: error])
            }
            throw NSError(domain: "ChatAPI", code: http.statusCode, userInfo: [NSLocalizedDescriptionKey: "请求失败(\(http.statusCode))"])
        }
    }
}
