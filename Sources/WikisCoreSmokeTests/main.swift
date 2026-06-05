import Foundation
import WikisCore

enum SmokeFailure: Error, CustomStringConvertible {
    case missingArgument
    case unexpectedTopicCount(Int)
    case validationIssues([String])
    case missingGestureTargets(String)
    case missingBlackHolePath
    case teleportStayedInScience
    case unexpectedReasonCode(String)
    case missingPrefetchCandidates
    case frontierCapFailed(Int)
    case repeatedRecentTopic(String)

    var description: String {
        switch self {
        case .missingArgument:
            "Usage: WikisCoreSmokeTests data/graph/seed_graph.json"
        case .unexpectedTopicCount(let count):
            "Expected 100 topics, found \(count)"
        case .validationIssues(let issues):
            "Graph has validation issues: \(issues)"
        case .missingGestureTargets(let topicId):
            "Missing gesture targets for \(topicId)"
        case .missingBlackHolePath:
            "Could not resolve black-hole down/right/left paths"
        case .teleportStayedInScience:
            "Black-hole teleport should leave Science"
        case .unexpectedReasonCode(let reasonCode):
            "Unexpected traversal reason code: \(reasonCode)"
        case .missingPrefetchCandidates:
            "Traversal decision did not include prefetch candidates"
        case .frontierCapFailed(let count):
            "Background frontier exceeded cap: \(count)"
        case .repeatedRecentTopic(let topicId):
            "Traversal repeated a recent topic: \(topicId)"
        }
    }
}

func run() throws {
    guard CommandLine.arguments.count >= 2 else {
        throw SmokeFailure.missingArgument
    }

    let url = URL(fileURLWithPath: CommandLine.arguments[1])
    let graph = try GraphLoader.load(from: url)

    guard graph.topics.count == 100 else {
        throw SmokeFailure.unexpectedTopicCount(graph.topics.count)
    }
    guard graph.stats.validationIssues.isEmpty else {
        throw SmokeFailure.validationIssues(graph.stats.validationIssues)
    }

    for topicId in graph.starterPool {
        guard let targets = graph.gestureIndex[topicId],
              !targets.down.isEmpty,
              !targets.right.isEmpty,
              !targets.left.isEmpty
        else {
            throw SmokeFailure.missingGestureTargets(topicId)
        }
    }

    let navigator = GraphNavigator(graph: graph)
    let context = TraversalContext(
        exploredTopicIds: ["black-hole"],
        savedTopicIds: [],
        allowPrototypeContent: true,
        frontierLimit: 2,
        prefetchLimit: 3
    )
    guard let downDecision = navigator.decision(from: "black-hole", gesture: .down, context: context),
          let rightDecision = navigator.decision(from: "black-hole", gesture: .right, context: context),
          let leftDecision = navigator.decision(from: "black-hole", gesture: .left, context: context)
    else {
        throw SmokeFailure.missingBlackHolePath
    }
    let down = downDecision.nextTopic
    let right = rightDecision.nextTopic
    let left = leftDecision.nextTopic

    guard left.pillar != .science else {
        throw SmokeFailure.teleportStayedInScience
    }
    guard downDecision.reasonCode == .bestDeeperEdge else {
        throw SmokeFailure.unexpectedReasonCode(downDecision.reasonCode.rawValue)
    }
    guard rightDecision.reasonCode == .bestNeighborEdge else {
        throw SmokeFailure.unexpectedReasonCode(rightDecision.reasonCode.rawValue)
    }
    guard leftDecision.reasonCode == .bestTeleportEdge else {
        throw SmokeFailure.unexpectedReasonCode(leftDecision.reasonCode.rawValue)
    }
    guard !downDecision.prefetchTopicIds.isEmpty else {
        throw SmokeFailure.missingPrefetchCandidates
    }
    guard downDecision.backgroundIngestionTopics.count <= 2 else {
        throw SmokeFailure.frontierCapFailed(downDecision.backgroundIngestionTopics.count)
    }
    guard let frontierDecision = navigator.decision(from: "general-relativity", gesture: .right, context: context),
          !frontierDecision.backgroundIngestionTopics.isEmpty
    else {
        throw SmokeFailure.missingPrefetchCandidates
    }
    guard frontierDecision.backgroundIngestionTopics.count <= 2 else {
        throw SmokeFailure.frontierCapFailed(frontierDecision.backgroundIngestionTopics.count)
    }

    let repeatContext = TraversalContext(
        exploredTopicIds: ["black-hole", down.id, right.id],
        allowPrototypeContent: true
    )
    if let repeatedDecision = navigator.decision(from: "black-hole", gesture: .right, context: repeatContext),
       [down.id, right.id].contains(repeatedDecision.nextTopic.id) {
        throw SmokeFailure.repeatedRecentTopic(repeatedDecision.nextTopic.id)
    }

    print("WikisCore smoke test passed")
    print("topics: \(graph.topics.count)")
    print("black-hole down: \(down.title)")
    print("black-hole right: \(right.title)")
    print("black-hole left: \(left.title)")
    print("down reason: \(downDecision.reasonCode.rawValue)")
    print("prefetch: \(downDecision.prefetchTopicIds.joined(separator: ", "))")
    print("background frontier: \(downDecision.backgroundIngestionTopics.map(\.title).joined(separator: ", "))")
}

do {
    try run()
} catch {
    fputs("ERROR: \(error)\n", stderr)
    exit(1)
}
