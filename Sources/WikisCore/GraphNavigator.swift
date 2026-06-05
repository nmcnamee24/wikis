import Foundation

public struct TraversalContext: Sendable {
    public let exploredTopicIds: [String]
    public let savedTopicIds: Set<String>
    public let allowPrototypeContent: Bool
    public let frontierLimit: Int
    public let prefetchLimit: Int

    public init(
        exploredTopicIds: [String] = [],
        savedTopicIds: Set<String> = [],
        allowPrototypeContent: Bool = true,
        frontierLimit: Int = 2,
        prefetchLimit: Int = 3
    ) {
        self.exploredTopicIds = exploredTopicIds
        self.savedTopicIds = savedTopicIds
        self.allowPrototypeContent = allowPrototypeContent
        self.frontierLimit = max(0, frontierLimit)
        self.prefetchLimit = max(0, prefetchLimit)
    }
}

public struct TraversalDecision: Sendable, Equatable {
    public let gesture: NavigationGesture
    public let currentTopicId: String
    public let nextTopic: Topic
    public let reasonCode: TraversalReasonCode
    public let score: Double
    public let selectedEdge: TopicEdge?
    public let fallbackTopicIds: [String]
    public let prefetchTopicIds: [String]
    public let backgroundIngestionTopics: [CandidateTopic]
    public let fallbackWasUsed: Bool
    public let debugSummary: String
}

public enum TraversalReasonCode: String, Sendable, Codable {
    case bestDeeperEdge = "best_deeper_edge"
    case bestPrerequisiteEdge = "best_prerequisite_edge"
    case bestNeighborEdge = "best_neighbor_edge"
    case bestContrastEdge = "best_contrast_edge"
    case bestTeleportEdge = "best_teleport_edge"
    case fallbackSamePillar = "fallback_same_pillar"
    case fallbackCrossPillar = "fallback_cross_pillar"
    case fallbackAnyApproved = "fallback_any_approved"
}

private struct TraversalCandidate {
    let topic: Topic
    let edge: TopicEdge?
    let score: Double
    let reasonCode: TraversalReasonCode
}

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
        decision(
            from: currentTopicId,
            gesture: gesture,
            context: TraversalContext()
        )?.nextTopic
    }

    public func decision(
        from currentTopicId: String,
        gesture: NavigationGesture,
        context: TraversalContext = TraversalContext()
    ) -> TraversalDecision? {
        let currentTopic = graph.topic(id: currentTopicId)
        let candidates = rankedCandidates(
            from: currentTopicId,
            currentTopic: currentTopic,
            gesture: gesture,
            context: context
        )

        let selected = candidates.first ?? fallbackCandidate(
            from: currentTopicId,
            currentTopic: currentTopic,
            gesture: gesture,
            context: context
        )
        guard let selected else { return nil }

        let fallbackIds = candidates
            .dropFirst()
            .prefix(3)
            .map(\.topic.id)
        let prefetchIds = prefetchTopicIds(
            after: selected.topic.id,
            excluding: Set(context.exploredTopicIds + [currentTopicId, selected.topic.id]),
            limit: context.prefetchLimit
        )
        let backgroundTopics = backgroundIngestionTopics(
            from: currentTopicId,
            limit: context.frontierLimit
        )
        let fallbackWasUsed = selected.edge == nil

        return TraversalDecision(
            gesture: gesture,
            currentTopicId: currentTopicId,
            nextTopic: selected.topic,
            reasonCode: selected.reasonCode,
            score: selected.score,
            selectedEdge: selected.edge,
            fallbackTopicIds: Array(fallbackIds),
            prefetchTopicIds: prefetchIds,
            backgroundIngestionTopics: backgroundTopics,
            fallbackWasUsed: fallbackWasUsed,
            debugSummary: debugSummary(
                selected: selected,
                fallbackWasUsed: fallbackWasUsed,
                backgroundTopics: backgroundTopics
            )
        )
    }

    public func fallbackTopic(excluding currentTopicId: String, preferredPillar: Pillar?) -> Topic? {
        fallbackCandidate(
            from: currentTopicId,
            currentTopic: graph.topic(id: currentTopicId),
            gesture: .right,
            context: TraversalContext()
        )?.topic ?? approvedTopics(allowPrototypeContent: true).first { topic in
            topic.id != currentTopicId && (preferredPillar == nil || topic.pillar == preferredPillar)
        }
    }

    private func rankedCandidates(
        from currentTopicId: String,
        currentTopic: Topic?,
        gesture: NavigationGesture,
        context: TraversalContext
    ) -> [TraversalCandidate] {
        edges(from: currentTopicId, gesture: gesture)
            .compactMap { edge -> TraversalCandidate? in
                guard let topic = graph.topic(id: edge.to),
                      isAllowed(topic: topic, context: context)
                else { return nil }
                return TraversalCandidate(
                    topic: topic,
                    edge: edge,
                    score: score(edge: edge, topic: topic, currentTopic: currentTopic, gesture: gesture, context: context),
                    reasonCode: reasonCode(for: edge, gesture: gesture)
                )
            }
            .sorted { lhs, rhs in
                if lhs.score == rhs.score {
                    return lhs.topic.title < rhs.topic.title
                }
                return lhs.score > rhs.score
            }
    }

    private func edges(from topicId: String, gesture: NavigationGesture) -> [TopicEdge] {
        let desiredTypes = edgeTypes(for: gesture)
        return graph.edges
            .filter { edge in
                edge.from == topicId && desiredTypes.contains(edge.type) && edge.generationStatus != .failed
            }
            .sorted { lhs, rhs in
                let leftRank = lhs.rank ?? Int.max
                let rightRank = rhs.rank ?? Int.max
                if leftRank == rightRank {
                    return lhs.strength > rhs.strength
                }
                return leftRank < rightRank
            }
    }

    private func edgeTypes(for gesture: NavigationGesture) -> [EdgeType] {
        switch gesture {
        case .down:
            [.deeper, .prerequisite]
        case .right:
            [.neighbor, .contrast, .person, .place]
        case .left:
            [.teleport]
        }
    }

    private func score(
        edge: TopicEdge,
        topic: Topic,
        currentTopic: Topic?,
        gesture: NavigationGesture,
        context: TraversalContext
    ) -> Double {
        let edgeRelevance = min(max(edge.strength, 0), 1)
        let confidence = edge.confidence ?? edgeRelevance
        let topicQuality = qualityScore(topic)
        let sourceConfidence = sourceConfidence(topic)
        let novelty = noveltyScore(topic: topic, currentTopic: currentTopic, context: context)
        let visual = topic.visualStrength
        let savedAffinity = context.savedTopicIds.contains(topic.id) ? 0.08 : 0
        let repetitionPenalty = repetitionPenalty(topicId: topic.id, context: context)
        let sensitivityPenalty = sensitivityPenalty(topic: topic)
        let typeBonus = edgeTypeBonus(edge.type, gesture: gesture)

        switch gesture {
        case .down:
            return edgeRelevance * 0.42
                + confidence * 0.14
                + topicQuality * 0.16
                + sourceConfidence * 0.12
                + novelty * 0.08
                + visual * 0.04
                + typeBonus
                + savedAffinity
                - repetitionPenalty
                - sensitivityPenalty
        case .right:
            return edgeRelevance * 0.34
                + confidence * 0.14
                + topicQuality * 0.15
                + sourceConfidence * 0.10
                + novelty * 0.14
                + visual * 0.05
                + typeBonus
                + savedAffinity
                - repetitionPenalty
                - sensitivityPenalty
        case .left:
            return edgeRelevance * 0.24
                + confidence * 0.10
                + topicQuality * 0.14
                + sourceConfidence * 0.10
                + novelty * 0.30
                + visual * 0.07
                + typeBonus
                + savedAffinity
                - repetitionPenalty
                - sensitivityPenalty
        }
    }

    private func fallbackCandidate(
        from currentTopicId: String,
        currentTopic: Topic?,
        gesture: NavigationGesture,
        context: TraversalContext
    ) -> TraversalCandidate? {
        let excluded = Set(context.exploredTopicIds.suffix(8) + [currentTopicId])
        let topics = approvedTopics(allowPrototypeContent: context.allowPrototypeContent)
            .filter { !excluded.contains($0.id) }
        let preferred: [Topic]
        let reason: TraversalReasonCode
        switch gesture {
        case .down, .right:
            preferred = topics.filter { topic in
                currentTopic == nil || topic.pillar == currentTopic?.pillar
            }
            reason = .fallbackSamePillar
        case .left:
            preferred = topics.filter { topic in
                currentTopic == nil || topic.pillar != currentTopic?.pillar
            }
            reason = .fallbackCrossPillar
        }
        let topic = (preferred.isEmpty ? topics : preferred)
            .sorted { lhs, rhs in
                fallbackScore(topic: lhs, currentTopic: currentTopic, context: context, gesture: gesture)
                    > fallbackScore(topic: rhs, currentTopic: currentTopic, context: context, gesture: gesture)
            }
            .first
        guard let topic else { return nil }
        return TraversalCandidate(
            topic: topic,
            edge: nil,
            score: fallbackScore(topic: topic, currentTopic: currentTopic, context: context, gesture: gesture),
            reasonCode: preferred.isEmpty ? .fallbackAnyApproved : reason
        )
    }

    private func fallbackScore(
        topic: Topic,
        currentTopic: Topic?,
        context: TraversalContext,
        gesture: NavigationGesture
    ) -> Double {
        qualityScore(topic) * 0.35
            + sourceConfidence(topic) * 0.25
            + noveltyScore(topic: topic, currentTopic: currentTopic, context: context) * (gesture == .left ? 0.30 : 0.18)
            + topic.visualStrength * 0.10
            - repetitionPenalty(topicId: topic.id, context: context)
            - sensitivityPenalty(topic: topic)
    }

    private func prefetchTopicIds(after topicId: String, excluding: Set<String>, limit: Int) -> [String] {
        guard limit > 0 else { return [] }
        let edgeTargets = graph.edges
            .filter { $0.from == topicId && $0.generationStatus != .failed }
            .sorted { $0.strength > $1.strength }
            .compactMap { edge -> String? in
                guard !excluding.contains(edge.to),
                      let topic = graph.topic(id: edge.to),
                      topic.isProductionVisible
                else { return nil }
                return topic.id
            }
        var seen: Set<String> = []
        return edgeTargets.filter { seen.insert($0).inserted }.prefix(limit).map { $0 }
    }

    private func backgroundIngestionTopics(from topicId: String, limit: Int) -> [CandidateTopic] {
        guard limit > 0 else { return [] }
        return graph.candidateQueue
            .filter { $0.seenFrom.contains(topicId) }
            .sorted { lhs, rhs in
                if lhs.priority == rhs.priority {
                    return lhs.title < rhs.title
                }
                return lhs.priority > rhs.priority
            }
            .prefix(limit)
            .map { $0 }
    }

    private func approvedTopics(allowPrototypeContent: Bool) -> [Topic] {
        graph.topics.filter { topic in
            if topic.qualityStatus == "approved" {
                return true
            }
            return allowPrototypeContent && topic.qualityStatus == "prototype_pass"
        }
    }

    private func isAllowed(topic: Topic, context: TraversalContext) -> Bool {
        guard approvedTopics(allowPrototypeContent: context.allowPrototypeContent).contains(topic) else {
            return false
        }
        guard sourceConfidence(topic) >= 0.55 else {
            return false
        }
        guard topic.image.strategy == .wikipediaImage || topic.image.fallbackPillar != nil else {
            return false
        }
        return true
    }

    private func reasonCode(for edge: TopicEdge, gesture: NavigationGesture) -> TraversalReasonCode {
        switch (gesture, edge.type) {
        case (.down, .deeper):
            .bestDeeperEdge
        case (.down, .prerequisite):
            .bestPrerequisiteEdge
        case (.right, .neighbor), (.right, .person), (.right, .place):
            .bestNeighborEdge
        case (.right, .contrast):
            .bestContrastEdge
        case (.left, .teleport):
            .bestTeleportEdge
        default:
            .fallbackAnyApproved
        }
    }

    private func edgeTypeBonus(_ edgeType: EdgeType, gesture: NavigationGesture) -> Double {
        switch (gesture, edgeType) {
        case (.down, .deeper), (.right, .neighbor), (.left, .teleport):
            0.08
        case (.down, .prerequisite), (.right, .contrast):
            0.04
        case (.right, .person), (.right, .place):
            0.03
        default:
            0
        }
    }

    private func qualityScore(_ topic: Topic) -> Double {
        switch topic.qualityStatus {
        case "approved":
            1.0
        case "prototype_pass":
            0.86
        case "needs_review":
            0.58
        default:
            0
        }
    }

    private func sourceConfidence(_ topic: Topic) -> Double {
        topic.wikipedia.revisionId == nil ? 0.68 : 0.92
    }

    private func noveltyScore(topic: Topic, currentTopic: Topic?, context: TraversalContext) -> Double {
        var score = 0.72
        if let currentTopic, currentTopic.pillar != topic.pillar {
            score += 0.20
        }
        if context.savedTopicIds.contains(topic.id) {
            score -= 0.10
        }
        if context.exploredTopicIds.contains(topic.id) {
            score -= 0.35
        }
        return min(max(score, 0), 1)
    }

    private func repetitionPenalty(topicId: String, context: TraversalContext) -> Double {
        guard let lastSeenOffset = context.exploredTopicIds.reversed().enumerated().first(where: { $0.element == topicId })?.offset else {
            return 0
        }
        switch lastSeenOffset {
        case 0...2:
            return 0.75
        case 3...7:
            return 0.35
        default:
            return 0.12
        }
    }

    private func sensitivityPenalty(topic: Topic) -> Double {
        let text = "\(topic.title) \(topic.explanation)".lowercased()
        let sensitiveTerms = ["assassination", "war", "disease", "death", "violence"]
        return sensitiveTerms.contains { text.contains($0) } ? 0.08 : 0
    }

    private func debugSummary(
        selected: TraversalCandidate,
        fallbackWasUsed: Bool,
        backgroundTopics: [CandidateTopic]
    ) -> String {
        let route = selected.edge.map { "\($0.type.rawValue):\($0.id)" } ?? "fallback"
        let background = backgroundTopics.map(\.id).joined(separator: ",")
        return "route=\(route); reason=\(selected.reasonCode.rawValue); score=\(String(format: "%.3f", selected.score)); fallback=\(fallbackWasUsed); background=[\(background)]"
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
