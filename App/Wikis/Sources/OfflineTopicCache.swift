import Foundation
#if canImport(WikisCore)
import WikisCore
#endif

struct OfflineTopicCache {
    private let fileURL: URL
    private let maxTopics: Int

    init(
        fileManager: FileManager = .default,
        maxTopics: Int = 75,
        filename: String = "offline-topic-cache.json"
    ) {
        self.maxTopics = maxTopics
        let baseURL = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? fileManager.temporaryDirectory
        let directoryURL = baseURL.appending(path: "Wikis", directoryHint: .isDirectory)
        try? fileManager.createDirectory(at: directoryURL, withIntermediateDirectories: true)
        self.fileURL = directoryURL.appending(path: filename)
    }

    func snapshot() -> OfflineTopicSnapshot {
        guard let data = try? Data(contentsOf: fileURL),
              let snapshot = try? JSONDecoder().decode(OfflineTopicSnapshot.self, from: data)
        else {
            return OfflineTopicSnapshot()
        }
        return snapshot
    }

    func latestTopic() -> Topic? {
        let snapshot = snapshot()
        if let lastTopicId = snapshot.lastTopicId,
           let topic = snapshot.entries.first(where: { $0.topic.id == lastTopicId })?.topic {
            return topic
        }
        return snapshot.entries.sortedByRecency.first?.topic
    }

    func fallbackTopic(excluding excludedIds: Set<String>, preferredPillar: Pillar?, gesture: NavigationGesture) -> Topic? {
        let entries = snapshot().entries.sortedByRecency.filter { entry in
            !excludedIds.contains(entry.topic.id) && entry.topic.isProductionVisible
        }
        let preferred = entries.filter { entry in
            switch gesture {
            case .down, .right:
                preferredPillar == nil || entry.topic.pillar == preferredPillar
            case .left:
                preferredPillar == nil || entry.topic.pillar != preferredPillar
            }
        }
        return (preferred.first ?? entries.first)?.topic
    }

    func store(topic: Topic, markAsLast: Bool = true) {
        var snapshot = snapshot()
        snapshot.upsert(topic: topic, markAsLast: markAsLast, maxTopics: maxTopics)
        save(snapshot)
    }

    private func save(_ snapshot: OfflineTopicSnapshot) {
        guard let data = try? JSONEncoder().encode(snapshot) else { return }
        try? data.write(to: fileURL, options: [.atomic])
    }
}

struct OfflineTopicSnapshot: Codable {
    var schemaVersion: Int
    var lastTopicId: String?
    var entries: [OfflineTopicCacheEntry]

    init(schemaVersion: Int = 1, lastTopicId: String? = nil, entries: [OfflineTopicCacheEntry] = []) {
        self.schemaVersion = schemaVersion
        self.lastTopicId = lastTopicId
        self.entries = entries
    }

    mutating func upsert(topic: Topic, markAsLast: Bool, maxTopics: Int) {
        entries.removeAll { $0.topic.id == topic.id }
        entries.append(
            OfflineTopicCacheEntry(
                topic: topic,
                cachedAt: Date()
            )
        )
        entries = Array(entries.sortedByRecency.prefix(maxTopics))
        if markAsLast {
            lastTopicId = topic.id
        }
    }
}

struct OfflineTopicCacheEntry: Codable {
    let topic: Topic
    let cachedAt: Date
}

private extension Array where Element == OfflineTopicCacheEntry {
    var sortedByRecency: [OfflineTopicCacheEntry] {
        sorted { $0.cachedAt > $1.cachedAt }
    }
}
