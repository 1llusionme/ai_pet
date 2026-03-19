import SwiftUI

@main
struct MindShadowHybridApp: App {
    private let appConfig = AppConfig(
        apiBaseURL: URL(string: "https://api.example.com")!,
        webBaseURL: URL(string: "https://web.example.com")!
    )

    var body: some Scene {
        WindowGroup {
            RootTabView(config: appConfig)
        }
    }
}
