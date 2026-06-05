import Foundation
import SwiftUI
#if canImport(WikisCore)
import WikisCore
#endif

@MainActor
final class FeedStore: ObservableObject {
    @Published private(set) var graph: WikisGraph?
    @Published private(set) var currentTopic: Topic?
    @Published private(set) var exploredTopics: [Topic] = []
    @Published private(set) var savedTopicIds: Set<String> = []
    @Published var lastGestureLabel: String?
    @Published var loadingError: String?

    private var navigator: GraphNavigator?

    init() {
        loadGraph()
    }

    func loadGraph() {
        do {
            let graph = try GraphLoader.loadBundled()
            let navigator = GraphNavigator(graph: graph)
            self.graph = graph
            self.navigator = navigator
            let initialTopic = graph.topic(id: "black-hole") ?? navigator.initialTopic
            currentTopic = initialTopic
            exploredTopics = [initialTopic]
            loadingError = nil
        } catch {
            loadingError = "Seed graph could not be loaded."
        }
    }

    @discardableResult
    func navigate(_ gesture: NavigationGesture) -> Bool {
        guard let currentTopic, let nextTopic = navigator?.nextTopic(from: currentTopic.id, gesture: gesture) else {
            return false
        }
        withAnimation(.spring(response: 0.42, dampingFraction: 0.86)) {
            self.currentTopic = nextTopic
            self.exploredTopics.append(nextTopic)
            self.lastGestureLabel = gesture.label
        }
        return true
    }

    @discardableResult
    func goBack() -> Bool {
        guard exploredTopics.count > 1 else { return false }
        withAnimation(.spring(response: 0.42, dampingFraction: 0.86)) {
            exploredTopics.removeLast()
            currentTopic = exploredTopics.last
            lastGestureLabel = "Back"
        }
        return true
    }

    func toggleSaveCurrentTopic() {
        guard let currentTopic else { return }
        if savedTopicIds.contains(currentTopic.id) {
            savedTopicIds.remove(currentTopic.id)
        } else {
            savedTopicIds.insert(currentTopic.id)
        }
    }

    func isSaved(_ topic: Topic) -> Bool {
        savedTopicIds.contains(topic.id)
    }
}

extension NavigationGesture {
    var label: String {
        switch self {
        case .down: "Continue"
        case .right: "Explore"
        case .left: "Teleport"
        }
    }
}
