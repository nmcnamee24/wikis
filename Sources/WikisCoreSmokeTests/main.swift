import Foundation
import WikisCore

enum SmokeFailure: Error, CustomStringConvertible {
    case missingArgument
    case unexpectedTopicCount(Int)
    case validationIssues([String])
    case missingGestureTargets(String)
    case missingBlackHolePath
    case teleportStayedInScience

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
    guard let down = navigator.nextTopic(from: "black-hole", gesture: .down),
          let right = navigator.nextTopic(from: "black-hole", gesture: .right),
          let left = navigator.nextTopic(from: "black-hole", gesture: .left)
    else {
        throw SmokeFailure.missingBlackHolePath
    }
    guard left.pillar != .science else {
        throw SmokeFailure.teleportStayedInScience
    }

    print("WikisCore smoke test passed")
    print("topics: \(graph.topics.count)")
    print("black-hole down: \(down.title)")
    print("black-hole right: \(right.title)")
    print("black-hole left: \(left.title)")
}

do {
    try run()
} catch {
    fputs("ERROR: \(error)\n", stderr)
    exit(1)
}

