import SwiftUI
#if canImport(WikisCore)
import WikisCore
#endif

@main
struct WikisApp: App {
    var body: some Scene {
        WindowGroup {
            RootView()
        }
    }
}
