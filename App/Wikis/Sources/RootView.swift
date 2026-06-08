import SwiftUI
#if canImport(WikisCore)
import WikisCore
#endif

struct RootView: View {
    @StateObject private var store = FeedStore()
    @State private var selectedTab: AppTab = .home

    var body: some View {
        TabView(selection: $selectedTab) {
            FeedView(store: store)
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }
                .tag(AppTab.home)

            KnowledgeMapView(
                store: store,
                onOpenTopic: {
                    selectedTab = .home
                }
            )
                .tabItem {
                    Label("Map", systemImage: "point.3.connected.trianglepath.dotted")
                }
                .tag(AppTab.map)

            ProfileView(store: store)
                .tabItem {
                    Label("Profile", systemImage: "person")
                }
                .tag(AppTab.profile)
        }
        .tint(.wikisGold)
        .preferredColorScheme(.dark)
    }
}

private enum AppTab: Hashable {
    case home
    case map
    case profile
}
