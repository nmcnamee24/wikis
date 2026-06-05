import SwiftUI
#if canImport(WikisCore)
import WikisCore
#endif

struct RootView: View {
    @StateObject private var store = FeedStore()

    var body: some View {
        TabView {
            FeedView(store: store)
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }

            KnowledgeMapView(store: store)
                .tabItem {
                    Label("Map", systemImage: "point.3.connected.trianglepath.dotted")
                }

            ProfileView(store: store)
                .tabItem {
                    Label("Profile", systemImage: "person")
                }
        }
        .tint(.wikisGold)
        .preferredColorScheme(.dark)
    }
}
