import Foundation

public struct GraphNavigator: Sendable {
    public let graph: WikisGraph

    public init(graph: WikisGraph) {
        self.graph = graph
    }

    public var initialTopic: Topic {
        let initialId = graph.starterPool.first ?? graph.topics.first?.id
        guard let initialId, let topic = graph.topic(id: initialId) else {
            preconditionFailure("Seed graph has no topics")
        }
        return topic
    }

    public func nextTopic(from currentTopicId: String, gesture: NavigationGesture) -> Topic? {
        guard let targets = graph.gestureIndex[currentTopicId]?.targets(for: gesture) else {
            return fallbackTopic(excluding: currentTopicId, preferredPillar: nil)
        }
        for targetId in targets {
            if let topic = graph.topic(id: targetId) {
                return topic
            }
        }
        return fallbackTopic(excluding: currentTopicId, preferredPillar: nil)
    }

    public func fallbackTopic(excluding currentTopicId: String, preferredPillar: Pillar?) -> Topic? {
        graph.topics.first { topic in
            topic.id != currentTopicId && (preferredPillar == nil || topic.pillar == preferredPillar)
        } ?? graph.topics.first { $0.id != currentTopicId }
    }
}

public enum GraphLoadingError: Error, Equatable {
    case missingResource(String)
}

public enum GraphLoader {
    public static func load(from data: Data) throws -> WikisGraph {
        let decoder = JSONDecoder()
        return try decoder.decode(WikisGraph.self, from: data)
    }

    public static func load(from url: URL) throws -> WikisGraph {
        try load(from: Data(contentsOf: url))
    }

    public static func loadBundled(named resourceName: String = "seed_graph", in bundle: Bundle = .main) throws -> WikisGraph {
        guard let url = bundle.url(forResource: resourceName, withExtension: "json") else {
            throw GraphLoadingError.missingResource("\(resourceName).json")
        }
        return try load(from: url)
    }
}

