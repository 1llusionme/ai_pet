import SwiftUI

struct RootTabView: View {
    let config: AppConfig

    var body: some View {
        TabView {
            NativeChatView(baseURL: config.apiBaseURL)
                .tabItem {
                    Label("聊天", systemImage: "message.fill")
                }
            WebFeatureContainerView(
                title: "学习资产",
                initialURL: config.webURL(path: "/assets")
            )
            .tabItem {
                Label("资产", systemImage: "book.fill")
            }
            WebFeatureContainerView(
                title: "设置",
                initialURL: config.webURL(path: "/settings")
            )
            .tabItem {
                Label("设置", systemImage: "gearshape.fill")
            }
        }
    }
}
