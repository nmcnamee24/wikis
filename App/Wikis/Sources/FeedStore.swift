import Foundation
import SwiftUI
#if canImport(WikisCore)
import WikisCore
#endif

@MainActor
final class FeedStore: ObservableObject {
    @Published private(set) var currentTopic: Topic?
    @Published private(set) var exploredTopics: [Topic] = []
    @Published private(set) var savedTopicIds: Set<String> = []
    @Published var lastGestureLabel: String?
    @Published var loadingError: String?
    @Published private(set) var navigationRevision = 0

    private let apiBaseURL = URL(string: "https://wikis-production.up.railway.app")!
    private let sessionId = UUID().uuidString
    private let startupTopicId = "black-hole"

    init() {
        loadInitialTopic()
    }

    func loadInitialTopic() {
        Task {
            await loadTopicFromAPI(topicId: startupTopicId)
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

    private func apply(topic: Topic, gesture: NavigationGesture) {
        withAnimation(.spring(response: 0.42, dampingFraction: 0.86)) {
            self.currentTopic = topic
            self.exploredTopics.append(topic)
            self.lastGestureLabel = gesture.label
            self.navigationRevision += 1
        }
    }

    func openTopicFromMap(_ topic: Topic) {
        withAnimation(.spring(response: 0.42, dampingFraction: 0.86)) {
            if let existingIndex = exploredTopics.lastIndex(where: { $0.id == topic.id }) {
                exploredTopics = Array(exploredTopics.prefix(existingIndex + 1))
            } else {
                exploredTopics.append(topic)
            }
            currentTopic = topic
            lastGestureLabel = "Map"
            loadingError = nil
            navigationRevision += 1
        }
    }

    private func navigateUsingLiveAPI(
        from currentTopic: Topic,
        gesture: NavigationGesture,
        exploredTopicIds: [String],
        savedTopicIds: Set<String>
    ) async {
        do {
            let response = try await requestNextTopic(
                currentTopicId: currentTopic.id,
                gesture: gesture,
                exploredTopicIds: exploredTopicIds,
                savedTopicIds: Array(savedTopicIds)
            )
            apply(topic: response.nextTopic, gesture: gesture)
            Task {
                await recordExplorationEvent(
                    fromTopicId: currentTopic.id,
                    toTopicId: response.nextTopic.id,
                    gesture: gesture,
                    reasonCode: response.reasonCode
                )
            }
            loadingError = nil
        } catch {
            loadingError = "No Supabase route is available for this gesture."
        }
    }

    private func loadTopicFromAPI(topicId: String) async {
        do {
            let topic = try await requestTopic(topicId: topicId)
            withAnimation(.easeInOut(duration: 0.24)) {
                currentTopic = topic
                exploredTopics = [topic]
                navigationRevision += 1
            }
            loadingError = nil
        } catch {
            loadingError = "Supabase topic could not be loaded."
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
                allowPrototypeContent: true
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
    let allowPrototypeContent: Bool
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
}
