import SwiftUI

struct NativeChatView: View {
    @StateObject private var viewModel: ChatViewModel

    init(baseURL: URL) {
        _viewModel = StateObject(wrappedValue: ChatViewModel(api: ChatAPI(baseURL: baseURL)))
    }

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        ForEach(viewModel.messages) { message in
                            messageBubble(message)
                                .id(message.id)
                        }
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 14)
                }
                .onChange(of: viewModel.messages.count) {
                    if let last = viewModel.messages.last {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }
            if let error = viewModel.errorText, !error.isEmpty {
                Text(error)
                    .font(.footnote)
                    .foregroundStyle(.red)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
            }
            composer
        }
        .task {
            await viewModel.bootstrap()
        }
    }

    private var header: some View {
        HStack {
            HStack(spacing: 8) {
                Circle()
                    .fill(viewModel.isModelReady ? .green : .red)
                    .frame(width: 10, height: 10)
                Text("你一定要上岸！")
                    .font(.headline)
                    .fontWeight(.bold)
            }
            Spacer()
            Text(viewModel.modeText)
                .font(.footnote)
                .foregroundStyle(.secondary)
            Button("新对话") {
                viewModel.createNewConversation()
            }
            .buttonStyle(.bordered)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
    }

    private var composer: some View {
        HStack(alignment: .bottom, spacing: 8) {
            TextField("输入你的问题", text: $viewModel.inputText, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(1...5)
            Button {
                Task {
                    await viewModel.send()
                }
            } label: {
                if viewModel.isSending {
                    ProgressView()
                        .frame(width: 22, height: 22)
                } else {
                    Image(systemName: "paperplane.fill")
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(viewModel.isSending)
        }
        .padding(12)
    }

    private func messageBubble(_ message: ChatMessage) -> some View {
        HStack {
            if message.role == .user {
                Spacer(minLength: 30)
            }
            VStack(alignment: .leading, spacing: 6) {
                Text(roleText(message.role))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(message.isTyping && message.content.isEmpty ? "正在输入..." : message.content)
                    .font(.body)
                    .foregroundStyle(.primary)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(backgroundColor(message.role))
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            if message.role != .user {
                Spacer(minLength: 30)
            }
        }
    }

    private func roleText(_ role: ChatRole) -> String {
        switch role {
        case .user:
            return "我"
        case .ai:
            return "MindShadow"
        case .system:
            return "系统"
        }
    }

    private func backgroundColor(_ role: ChatRole) -> Color {
        switch role {
        case .user:
            return Color.blue.opacity(0.16)
        case .ai:
            return Color.gray.opacity(0.16)
        case .system:
            return Color.orange.opacity(0.18)
        }
    }
}
