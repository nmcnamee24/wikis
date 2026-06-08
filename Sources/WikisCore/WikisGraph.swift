import Foundation

public struct WikisGraph: Codable, Sendable {
    public let schemaVersion: Int
    public let graphId: String
    public let description: String
    public let topics: [Topic]
    public let edges: [TopicEdge]
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

    public var isProductionVisible: Bool {
        qualityStatus == "approved" || qualityStatus == "prototype_pass"
    }

    public var visualStrength: Double {
        switch image.strategy {
        case .wikipediaImage:
            image.selected?.qualityScore ?? 0.75
        case .pillarBackground:
            0.48
        }
    }
}

public enum Pillar: String, Codable, CaseIterable, Sendable {
    case science
    case literature
    case culture
    case society
    case history

    public var displayName: String {
        rawValue.capitalized
    }
}

public enum HookType: String, Codable, Sendable {
    case whyItMatters = "why_it_matters"
    case scientistsStillDontKnow = "scientists_still_dont_know"
    case theTwist = "the_twist"
    case theSurprisingPart = "the_surprising_part"

    public var displayPrefix: String {
        switch self {
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
    public let rank: Int?
    public let confidence: Double?
    public let generationStatus: GenerationStatus?
    public let generationVersion: String?
    public let generationHash: String?

    public init(
        id: String,
        from: String,
        to: String,
        type: EdgeType,
        strength: Double,
        reason: String,
        rank: Int? = nil,
        confidence: Double? = nil,
        generationStatus: GenerationStatus? = nil,
        generationVersion: String? = nil,
        generationHash: String? = nil
    ) {
        self.id = id
        self.from = from
        self.to = to
        self.type = type
        self.strength = strength
        self.reason = reason
        self.rank = rank
        self.confidence = confidence
        self.generationStatus = generationStatus
        self.generationVersion = generationVersion
        self.generationHash = generationHash
    }

    private enum CodingKeys: String, CodingKey {
        case id
        case from
        case to
        case type
        case strength
        case reason
        case rank
        case confidence
        case generationStatus
        case generationVersion
        case generationHash
    }
}

public enum GenerationStatus: String, Codable, Sendable {
    case missing
    case provisional
    case generating
    case ready
    case failed
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

public enum NavigationGesture: Sendable, Equatable, Codable {
    case down
    case right
    case left
}

public struct GraphStats: Codable, Equatable, Sendable {
    public let topicCount: Int
    public let edgeCount: Int
    public let pillarCounts: [String: Int]
    public let validationIssues: [String]
}
