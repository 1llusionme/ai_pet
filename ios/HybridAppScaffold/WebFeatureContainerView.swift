import SwiftUI
import WebKit

struct WebFeatureContainerView: View {
    let title: String
    let initialURL: URL
    @State private var isLoading = true
    @State private var hasError = false
    @State private var reloadToken = UUID()

    var body: some View {
        NavigationStack {
            ZStack {
                HybridWebView(
                    url: initialURL,
                    isLoading: $isLoading,
                    hasError: $hasError,
                    reloadToken: reloadToken
                )
                if isLoading {
                    ProgressView("加载中")
                }
                if hasError {
                    VStack(spacing: 10) {
                        Text("页面加载失败")
                            .font(.headline)
                        Button("重试") {
                            hasError = false
                            isLoading = true
                            reloadToken = UUID()
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    .padding(16)
                    .background(.thinMaterial)
                    .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                }
            }
            .navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}

struct HybridWebView: UIViewRepresentable {
    let url: URL
    @Binding var isLoading: Bool
    @Binding var hasError: Bool
    let reloadToken: UUID

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.defaultWebpagePreferences.allowsContentJavaScript = true
        let view = WKWebView(frame: .zero, configuration: config)
        view.navigationDelegate = context.coordinator
        view.load(URLRequest(url: url))
        return view
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        context.coordinator.syncParent(parent: self)
        context.coordinator.handleReloadToken(reloadToken, webView: webView, url: url)
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        private var parent: HybridWebView
        private var lastReloadToken: UUID?

        init(parent: HybridWebView) {
            self.parent = parent
        }

        func syncParent(parent: HybridWebView) {
            self.parent = parent
        }

        func handleReloadToken(_ token: UUID, webView: WKWebView, url: URL) {
            if token != lastReloadToken {
                lastReloadToken = token
                webView.load(URLRequest(url: url))
            }
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            parent.isLoading = true
            parent.hasError = false
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.isLoading = false
            parent.hasError = false
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            parent.isLoading = false
            parent.hasError = true
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            parent.isLoading = false
            parent.hasError = true
        }
    }
}
