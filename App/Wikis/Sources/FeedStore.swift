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
    @Published private(set) var liveGenerationStatus: String?
    @Published private(set) var navigationRevision = 0

    private var navigator: GraphNavigator?
    private let apiBaseURL = URL(string: "https://wikis-production.up.railway.app")!
    private let useLiveAPI = true
    private let sessionId = UUID().uuidString

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
        guard let currentTopic else {
            return false
        }
        let exploredIds = exploredTopics.map(\.id)
        let savedIds = savedTopicIds
        Task {
            await navigateUsingLiveAPI(
                from: currentTopic,
                gesture: gesture,
                exploredTopicIds: exploredIds,
                savedTopicIds: savedIds
            )
        }
        return true
    }

    private func localDecision(from currentTopic: Topic, gesture: NavigationGesture) -> TraversalDecision? {
        let context = TraversalContext(
            exploredTopicIds: exploredTopics.map(\.id),
            savedTopicIds: savedTopicIds,
            allowPrototypeContent: true,
            frontierLimit: 2,
            prefetchLimit: 3
        )
        return navigator?.decision(from: currentTopic.id, gesture: gesture, context: context)
    }

    private func apply(topic: Topic, gesture: NavigationGesture, liveGeneration: LiveGenerationStatus? = nil) {
        withAnimation(.spring(response: 0.42, dampingFraction: 0.86)) {
            self.currentTopic = topic
            self.exploredTopics.append(topic)
            self.lastGestureLabel = gesture.label
            self.navigationRevision += 1
        }
        if topic.isPendingCandidate {
            liveGenerationStatus = "Generating \(topic.title)..."
        } else if let liveGeneration {
            switch liveGeneration.status {
            case "scheduled":
                let titleList = liveGeneration.candidateTitles.compactMap { $0 }.joined(separator: ", ")
                liveGenerationStatus = titleList.isEmpty ? "Live expansion scheduled" : "Live expansion scheduled: \(titleList)"
            default:
                liveGenerationStatus = nil
            }
        }
    }

    private func navigateUsingLiveAPI(
        from currentTopic: Topic,
        gesture: NavigationGesture,
        exploredTopicIds: [String],
        savedTopicIds: Set<String>
    ) async {
        guard useLiveAPI else {
            if let decision = localDecision(from: currentTopic, gesture: gesture) {
                apply(topic: decision.nextTopic, gesture: gesture)
            }
            return
        }

        do {
            let response = try await requestNextTopic(
                currentTopicId: currentTopic.id,
                gesture: gesture,
                exploredTopicIds: exploredTopicIds,
                savedTopicIds: Array(savedTopicIds)
            )
            apply(topic: response.nextTopic, gesture: gesture, liveGeneration: response.liveGeneration)
            Task {
                await recordExplorationEvent(
                    fromTopicId: currentTopic.id,
                    toTopicId: response.nextTopic.id,
                    gesture: gesture,
                    reasonCode: response.reasonCode
                )
            }
            if response.nextTopic.isPendingCandidate {
                await pollPendingTopic(topicId: response.nextTopic.id)
            }
            loadingError = nil
        } catch {
            if let decision = localDecision(from: currentTopic, gesture: gesture) {
                apply(topic: decision.nextTopic, gesture: gesture)
                loadingError = "Using offline graph. Live API unavailable."
            } else {
                loadingError = "Could not load the next topic."
            }
        }
    }

    private func requestNextTopic(
        currentTopicId: String,
        gesture: NavigationGesture,
        exploredTopicIds: [String],
        savedTopicIds: [String]
    ) async throws -> FeedNextResponse {
        var request = URLRequest(url: apiBaseURL.appending(path: "/v1/feed/next"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 12
        request.httpBody = try JSONEncoder().encode(
            FeedNextAPIRequest(
                currentTopicId: currentTopicId,
                gesture: gesture.apiValue,
                exploredTopicIds: exploredTopicIds,
                savedTopicIds: savedTopicIds,
                frontierLimit: 2,
                prefetchLimit: 3,
                allowPrototypeContent: true,
                allowPendingCandidateCards: true,
                liveGenerationEnabled: true,
                liveGenerationLimit: 1
            )
        )

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              (200..<300).contains(httpResponse.statusCode)
        else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(FeedNextResponse.self, from: data)
    }

    private func requestTopic(topicId: String) async throws -> Topic {
        var request = URLRequest(url: apiBaseURL.appending(path: "/v1/topics/\(topicId)"))
        request.httpMethod = "GET"
        request.timeoutInterval = 8

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              (200..<300).contains(httpResponse.statusCode)
        else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(Topic.self, from: data)
    }

    private func pollPendingTopic(topicId: String) async {
        let delays: [UInt64] = [2, 4, 6, 8, 10]
        for delay in delays {
            try? await Task.sleep(nanoseconds: delay * 1_000_000_000)
            guard currentTopic?.id == topicId else { return }
            do {
                let topic = try await requestTopic(topicId: topicId)
                guard !topic.isPendingCandidate, currentTopic?.id == topicId else { return }
                replaceCurrentTopic(with: topic)
                return
            } catch {
                continue
            }
        }
    }

    private func replaceCurrentTopic(with topic: Topic) {
        withAnimation(.easeInOut(duration: 0.24)) {
            currentTopic = topic
            if let lastIndex = exploredTopics.lastIndex(where: { $0.id == topic.id }) {
                exploredTopics[lastIndex] = topic
            }
            if liveGenerationStatus != nil {
                liveGenerationStatus = nil
            }
        }
    }

    private func recordExplorationEvent(
        fromTopicId: String,
        toTopicId: String,
        gesture: NavigationGesture,
        reasonCode: String
    ) async {
        do {
            var request = URLRequest(url: apiBaseURL.appending(path: "/v1/events"))
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.timeoutInterval = 8
            request.httpBody = try JSONEncoder().encode(
                ExplorationEventAPIRequest(
                    sessionId: sessionId,
                    anonymousSessionId: sessionId,
                    fromTopicId: fromTopicId,
                    toTopicId: toTopicId,
                    gesture: gesture.apiValue,
                    reasonCode: reasonCode,
                    dwellMs: nil,
                    saved: false,
                    clientEventAt: ISO8601DateFormatter().string(from: Date())
                )
            )
            _ = try await URLSession.shared.data(for: request)
        } catch {
            // Exploration tracking should never interrupt reading or navigation.
        }
    }

    @discardableResult
    func goBack() -> Bool {
        guard exploredTopics.count > 1 else { return false }
        withAnimation(.spring(response: 0.42, dampingFraction: 0.86)) {
            exploredTopics.removeLast()
            currentTopic = exploredTopics.last
            lastGestureLabel = "Back"
            navigationRevision += 1
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

    var apiValue: String {
        switch self {
        case .down: "down"
        case .right: "right"
        case .left: "left"
        }
    }
}

private struct FeedNextAPIRequest: Encodable {
    let currentTopicId: String
    let gesture: String
    let exploredTopicIds: [String]
    let savedTopicIds: [String]
    let frontierLimit: Int
    let prefetchLimit: Int
    let allowPrototypeContent: Bool
    let allowPendingCandidateCards: Bool
    let liveGenerationEnabled: Bool
    let liveGenerationLimit: Int
}

private struct ExplorationEventAPIRequest: Encodable {
    let sessionId: String
    let anonymousSessionId: String
    let fromTopicId: String
    let toTopicId: String
    let gesture: String
    let reasonCode: String
    let dwellMs: Int?
    let saved: Bool
    let clientEventAt: String
}

private struct FeedNextResponse: Decodable {
    let nextTopicId: String
    let nextTopic: Topic
    let reasonCode: String
    let gesture: String
    let liveGeneration: LiveGenerationStatus?
}

private struct LiveGenerationStatus: Decodable {
    let status: String
    let limit: Int
    let candidateTitles: [String?]
}

private extension Topic {
    var isPendingCandidate: Bool {
        qualityStatus == "pending_candidate"
    }
}
