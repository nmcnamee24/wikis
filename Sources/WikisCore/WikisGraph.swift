import Foundation

public struct WikisGraph: Codable, Sendable {
    public let schemaVersion: Int
    public let graphId: String
    public let description: String
    public let topics: [Topic]
    public let edges: [TopicEdge]
    public let gestureIndex: [String: GestureTargets]
    public let starterPool: [String]
    public let candidateQueue: [CandidateTopic]
    public let stats: GraphStats

    public var topicsById: [String: Topic] {
        Dictionary(uniqueKeysWithValues: topics.map { ($0.id, $0) })
    }

    public func topic(id: String) -> Topic? {
        topicsById[id]
    }
}

public struct Topic: Codable, Identifiable, Equatable, Sendable {
    public let id: String
    public let title: String
    public let pillar: Pillar
    public let explanation: String
    public let hookType: HookType
    public let hook: String
    public let readingSeconds: Int
    public let qualityStatus: String
    public let wikipedia: WikipediaSource
    public let image: ImageDecision
}

public enum Pillar: String, Codable, CaseIterable, Sendable {
    case science
    case literature
    case society
    case history

    public var displayName: String {
        rawValue.capitalized
    }
}

public enum HookType: String, Codable, Sendable {
    case theWeirdPart = "the_weird_part"
    case whyItMatters = "why_it_matters"
    case scientistsStillDontKnow = "scientists_still_dont_know"
    case theTwist = "the_twist"
    case theSurprisingPart = "the_surprising_part"

    public var displayPrefix: String {
        switch self {
        case .theWeirdPart: "The weird part:"
        case .whyItMatters: "Why it matters:"
        case .scientistsStillDontKnow: "Scientists still don't know:"
        case .theTwist: "The twist:"
        case .theSurprisingPart: "The surprising part:"
        }
    }
}

public struct WikipediaSource: Codable, Equatable, Sendable {
    public let title: String
    public let pageId: Int
    public let revisionId: Int?
}

public struct ImageDecision: Codable, Equatable, Sendable {
    public let strategy: ImageStrategy
    public let selected: SelectedImage?
    public let fallbackPillar: Pillar?
    public let reason: String?
}

public enum ImageStrategy: String, Codable, Sendable {
    case wikipediaImage = "wikipedia_image"
    case pillarBackground = "pillar_background"
}

public struct SelectedImage: Codable, Equatable, Sendable {
    public let source: String
    public let title: String?
    public let url: URL
    public let thumbnailUrl: URL?
    public let width: Int?
    public let height: Int?
    public let qualityScore: Double
    public let rejectionReasons: [String]
}

public struct TopicEdge: Codable, Identifiable, Equatable, Sendable {
    public let id: String
    public let from: String
    public let to: String
    public let type: EdgeType
    public let strength: Double
    public let reason: String
}

public enum EdgeType: String, Codable, Sendable {
    case deeper
    case neighbor
    case teleport
    case prerequisite
    case contrast
    case person
    case place
}

public struct GestureTargets: Codable, Equatable, Sendable {
    public let down: [String]
    public let right: [String]
    public let left: [String]

    public func targets(for gesture: NavigationGesture) -> [String] {
        switch gesture {
        case .down: down
        case .right: right
        case .left: left
        }
    }
}

public enum NavigationGesture: Sendable {
    case down
    case right
    case left
}

public struct CandidateTopic: Codable, Identifiable, Equatable, Sendable {
    public let id: String
    public let title: String
    public let source: String
    public let seenFrom: [String]
    public let priority: Int
}

public struct GraphStats: Codable, Equatable, Sendable {
    public let topicCount: Int
    public let edgeCount: Int
    public let candidateQueueCount: Int
    public let pillarCounts: [String: Int]
    public let validationIssues: [String]
}

