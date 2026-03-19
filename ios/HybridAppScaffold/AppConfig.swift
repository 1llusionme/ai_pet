import Foundation

struct AppConfig {
    let apiBaseURL: URL
    let webBaseURL: URL

    var webFeatureURL: URL {
        webBaseURL.appending(path: "/")
    }

    func webURL(path: String) -> URL {
        webBaseURL.appending(path: path)
    }
}
