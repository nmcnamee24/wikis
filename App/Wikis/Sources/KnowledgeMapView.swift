import SwiftUI
#if canImport(WikisCore)
import WikisCore
#endif

struct KnowledgeMapView: View {
    @ObservedObject var store: FeedStore
    let onOpenTopic: () -> Void
    @State private var selectedTopic: Topic?
    @State private var pendingSingleTap: Task<Void, Never>?

    var body: some View {
        NavigationStack {
            GeometryReader { geometry in
                let layout = KnowledgeMapLayout.make(
                    exploredTopics: store.exploredTopics,
                    graph: store.graph,
                    size: geometry.size,
                    focusedTopicId: selectedTopic?.id
                )
                let previewTopic = selectedTopic ?? store.currentTopic

                ZStack {
                    MapBackground()

                    ZStack {
                        ForEach(layout.links) { link in
                            MapLinkShape(from: link.from, to: link.to)
                                .stroke(
                                    link.color,
                                    style: StrokeStyle(
                                        lineWidth: link.isFrontier ? 1.1 : 2.1,
                                        lineCap: .round,
                                        dash: link.isFrontier ? [6, 7] : []
                                    )
                                )
                                .opacity(link.isFrontier ? 0.32 : 0.78)
                        }

                        ForEach(layout.nodes) { node in
                            MapNodeView(
                                node: node,
                                isSelected: node.topic.id == selectedTopic?.id,
                                onSelect: {
                                    select(node.topic)
                                },
                                onOpen: {
                                    open(node.topic)
                                }
                            )
                                .position(node.position)
                                .transition(.scale(scale: 0.72).combined(with: .opacity))
                        }
                    }
                    .scaleEffect(selectedTopic == nil ? 1 : 1.08)
                    .padding(.top, 8)
                    .animation(.spring(response: 0.48, dampingFraction: 0.84), value: store.navigationRevision)
                    .animation(.spring(response: 0.42, dampingFraction: 0.84), value: selectedTopic?.id)

                    VStack(alignment: .leading, spacing: 0) {
                        MapHeader(
                            exploredCount: store.exploredTopics.count,
                            frontierCount: layout.frontierCount,
                            currentTitle: store.currentTopic?.title ?? "No topic"
                        )
                        .padding(.horizontal, 18)
                        .padding(.top, 18)

                        Spacer()

                        if let previewTopic {
                            MapPreviewCard(
                                topic: previewTopic,
                                isFocused: selectedTopic != nil,
                                accessibleCount: layout.accessibleCount,
                                onClose: {
                                    clearSelection()
                                },
                                onOpen: {
                                    open(previewTopic)
                                }
                            )
                            .padding(.horizontal, 18)
                            .padding(.bottom, 10)
                            .transition(.move(edge: .bottom).combined(with: .opacity))
                        }

                        MapRouteStrip(
                            topics: store.exploredTopics.suffix(5).map { $0 },
                            selectedTopicId: selectedTopic?.id,
                            onSelect: select,
                            onOpen: open
                        )
                            .padding(.horizontal, 18)
                            .padding(.bottom, 18)
                    }
                }
                .frame(width: geometry.size.width, height: geometry.size.height)
            }
            .background(Color.wikisInk)
            .mapNavigationChromeHidden()
        }
    }

    private func select(_ topic: Topic) {
        pendingSingleTap?.cancel()
        pendingSingleTap = Task { @MainActor in
            try? await Task.sleep(nanoseconds: 180_000_000)
            guard !Task.isCancelled else { return }
            selectedTopic = topic
        }
    }

    private func open(_ topic: Topic) {
        pendingSingleTap?.cancel()
        selectedTopic = topic
        store.openTopicFromMap(topic)
        onOpenTopic()
    }

    private func clearSelection() {
        pendingSingleTap?.cancel()
        selectedTopic = nil
    }
}

private extension View {
    @ViewBuilder
    func mapNavigationChromeHidden() -> some View {
        #if os(iOS)
        self
            .navigationBarTitleDisplayMode(.inline)
            .toolbar(.hidden, for: .navigationBar)
        #else
        self
        #endif
    }
}

private struct MapHeader: View {
    let exploredCount: Int
    let frontierCount: Int
    let currentTitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 14) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("Knowledge Map")
                        .font(.system(size: 28, weight: .bold))
                        .foregroundStyle(Color.wikisCream)

                    Text("Revealing from \(currentTitle)")
                        .font(.system(size: 14, weight: .medium))
                        .lineLimit(1)
                        .foregroundStyle(.white.opacity(0.62))
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 4) {
                    Text("\(exploredCount)")
                        .font(.system(size: 24, weight: .bold, design: .rounded))
                        .foregroundStyle(Color.wikisGold)
                    Text("seen")
                        .font(.system(size: 11, weight: .semibold))
                        .textCase(.uppercase)
                        .foregroundStyle(.white.opacity(0.48))
                }
            }

            HStack(spacing: 16) {
                MapLegendDot(color: .wikisGold, label: "Path")
                MapLegendDot(color: .wikisBlue, label: "Neighbor")
                MapLegendDot(color: .white.opacity(0.34), label: "\(frontierCount) nearby")
            }
        }
        .padding(16)
        .background(.black.opacity(0.30), in: RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(.white.opacity(0.10), lineWidth: 1)
        )
    }
}

private struct MapLegendDot: View {
    let color: Color
    let label: String

    var body: some View {
        HStack(spacing: 6) {
            Circle()
                .fill(color)
                .frame(width: 7, height: 7)
            Text(label)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(.white.opacity(0.62))
        }
    }
}

private struct MapRouteStrip: View {
    let topics: [Topic]
    let selectedTopicId: String?
    let onSelect: (Topic) -> Void
    let onOpen: (Topic) -> Void

    var body: some View {
        if !topics.isEmpty {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(Array(topics.enumerated()), id: \.element.id) { index, topic in
                        HStack(spacing: 7) {
                            Circle()
                                .fill(topic.pillar.accentColor)
                                .frame(width: 8, height: 8)
                            Text(topic.title)
                                .font(.system(size: 13, weight: .semibold))
                                .lineLimit(1)
                        }
                        .foregroundStyle(isEmphasized(topic, index: index) ? Color.wikisInk : Color.white.opacity(0.78))
                        .padding(.horizontal, 11)
                        .padding(.vertical, 9)
                        .background(
                            isEmphasized(topic, index: index) ? Color.wikisGold : .white.opacity(0.08),
                            in: RoundedRectangle(cornerRadius: 8)
                        )
                        .onTapGesture(count: 2) {
                            onOpen(topic)
                        }
                        .onTapGesture(count: 1) {
                            onSelect(topic)
                        }
                    }
                }
            }
        }
    }

    private func isEmphasized(_ topic: Topic, index: Int) -> Bool {
        topic.id == selectedTopicId || (selectedTopicId == nil && index == topics.count - 1)
    }
}

private struct MapPreviewCard: View {
    let topic: Topic
    let isFocused: Bool
    let accessibleCount: Int
    let onClose: () -> Void
    let onOpen: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 12) {
                Label(topic.pillar.displayName, systemImage: topic.pillar.symbolName)
                    .font(.system(size: 12, weight: .bold))
                    .foregroundStyle(topic.pillar.accentColor)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(.white.opacity(0.08), in: Capsule())

                Spacer()

                if isFocused {
                    Button(action: onClose) {
                        Image(systemName: "xmark")
                            .font(.system(size: 12, weight: .bold))
                            .frame(width: 28, height: 28)
                            .foregroundStyle(.white.opacity(0.74))
                            .background(.white.opacity(0.08), in: Circle())
                    }
                    .accessibilityLabel("Close map preview")
                }
            }

            VStack(alignment: .leading, spacing: 6) {
                Text(topic.title)
                    .font(.system(size: 21, weight: .bold))
                    .foregroundStyle(Color.wikisCream)
                    .lineLimit(2)

                Text(topic.hook)
                    .font(.system(size: 13, weight: .medium))
                    .lineLimit(3)
                    .foregroundStyle(.white.opacity(0.68))
            }

            HStack(spacing: 10) {
                Label("\(accessibleCount) routes", systemImage: "point.3.connected.trianglepath.dotted")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(.white.opacity(0.56))

                Spacer()

                Button(action: onOpen) {
                    Label("Open", systemImage: "arrow.up.forward")
                        .font(.system(size: 13, weight: .bold))
                        .foregroundStyle(Color.wikisInk)
                        .padding(.horizontal, 13)
                        .padding(.vertical, 9)
                        .background(Color.wikisGold, in: RoundedRectangle(cornerRadius: 8))
                }
                .accessibilityLabel("Open \(topic.title)")
            }
        }
        .padding(14)
        .background(.black.opacity(0.42), in: RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(.white.opacity(0.12), lineWidth: 1)
        )
    }
}

private struct MapNodeView: View {
    let node: KnowledgeMapNode
    let isSelected: Bool
    let onSelect: () -> Void
    let onOpen: () -> Void

    var body: some View {
        VStack(spacing: 6) {
            ZStack {
                Circle()
                    .fill(node.fill)
                    .frame(width: node.diameter, height: node.diameter)
                    .shadow(color: node.glow, radius: node.isCurrent ? 16 : 8)

                Circle()
                    .stroke(isSelected ? Color.wikisGold : node.stroke, lineWidth: isSelected ? 2.4 : node.isFrontier ? 1 : 1.6)
                    .frame(width: node.diameter + 5, height: node.diameter + 5)

                if node.isCurrent || isSelected {
                    Circle()
                        .stroke(Color.wikisGold.opacity(isSelected ? 0.38 : 0.28), lineWidth: isSelected ? 9 : 7)
                        .frame(width: node.diameter + 18, height: node.diameter + 18)
                }
            }

            Text(node.title)
                .font(.system(size: node.isFrontier ? 10 : 12, weight: node.isFrontier ? .medium : .semibold))
                .lineLimit(2)
                .multilineTextAlignment(.center)
                .foregroundStyle(node.isFrontier ? .white.opacity(0.44) : .white.opacity(0.88))
                .frame(width: node.isFrontier ? 86 : 112)
                .fixedSize(horizontal: false, vertical: true)
        }
        .contentShape(Rectangle())
        .onTapGesture(count: 2, perform: onOpen)
        .onTapGesture(count: 1, perform: onSelect)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(node.accessibilityLabel)
        .accessibilityAddTraits(.isButton)
    }
}

private struct MapBackground: View {
    var body: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color.wikisInk,
                    Color(red: 0.03, green: 0.05, blue: 0.09),
                    Color.black
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            Canvas { context, size in
                let spacing: CGFloat = 32
                var x: CGFloat = 0
                while x < size.width {
                    var y: CGFloat = 0
                    while y < size.height {
                        let rect = CGRect(x: x, y: y, width: 1.4, height: 1.4)
                        context.fill(Path(ellipseIn: rect), with: .color(.white.opacity(0.07)))
                        y += spacing
                    }
                    x += spacing
                }

                let center = CGPoint(x: size.width * 0.5, y: size.height * 0.52)
                for radius in stride(from: CGFloat(86), through: min(size.width, size.height) * 0.62, by: 86) {
                    let rect = CGRect(
                        x: center.x - radius,
                        y: center.y - radius * 0.74,
                        width: radius * 2,
                        height: radius * 1.48
                    )
                    context.stroke(
                        Path(ellipseIn: rect),
                        with: .color(.white.opacity(0.045)),
                        style: StrokeStyle(lineWidth: 1, dash: [4, 10])
                    )
                }
            }
            .ignoresSafeArea()
        }
    }
}

private struct MapLinkShape: Shape {
    let from: CGPoint
    let to: CGPoint

    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: from)
        let midpoint = CGPoint(x: (from.x + to.x) / 2, y: (from.y + to.y) / 2)
        let dx = to.x - from.x
        let dy = to.y - from.y
        let control = CGPoint(x: midpoint.x - dy * 0.08, y: midpoint.y + dx * 0.08)
        path.addQuadCurve(to: to, control: control)
        return path
    }
}

private struct KnowledgeMapLayout {
    let nodes: [KnowledgeMapNode]
    let links: [KnowledgeMapLink]
    let frontierCount: Int
    let accessibleCount: Int

    static func make(exploredTopics: [Topic], graph: WikisGraph?, size: CGSize, focusedTopicId: String?) -> KnowledgeMapLayout {
        guard !exploredTopics.isEmpty else {
            return KnowledgeMapLayout(nodes: [], links: [], frontierCount: 0, accessibleCount: 0)
        }

        let safeSize = CGSize(width: max(size.width, 1), height: max(size.height, 1))
        let exploredIds = Set(exploredTopics.map(\.id))
        let graphTopics = graph?.topicsById ?? [:]
        let focusedTopic = focusedTopicId.flatMap { topicId in
            exploredTopics.first { $0.id == topicId } ?? graphTopics[topicId]
        }

        if let focusedTopic {
            return focusedLayout(
                topic: focusedTopic,
                exploredTopics: exploredTopics,
                exploredIds: exploredIds,
                graph: graph,
                graphTopics: graphTopics,
                size: safeSize
            )
        }

        var nodes: [KnowledgeMapNode] = exploredTopics.enumerated().map { index, topic in
            KnowledgeMapNode(
                id: topic.id,
                topic: topic,
                title: topic.title,
                pillar: topic.pillar,
                position: exploredPosition(index: index, count: exploredTopics.count, size: safeSize),
                kind: index == exploredTopics.count - 1 ? .current : .explored
            )
        }
        var links: [KnowledgeMapLink] = []

        let nodesById = Dictionary(uniqueKeysWithValues: nodes.map { ($0.id, $0) })
        for pair in zip(exploredTopics, exploredTopics.dropFirst()) {
            guard let from = nodesById[pair.0.id], let to = nodesById[pair.1.id] else { continue }
            links.append(
                KnowledgeMapLink(
                    id: "\(pair.0.id)-path-\(pair.1.id)",
                    from: from.position,
                    to: to.position,
                    edgeType: .deeper,
                    isFrontier: false
                )
            )
        }

        guard let graph else {
            return KnowledgeMapLayout(nodes: nodes, links: links, frontierCount: 0, accessibleCount: 0)
        }

        let exploredNodePositions = Dictionary(uniqueKeysWithValues: nodes.map { ($0.id, $0.position) })
        var frontierIds = Set<String>()
        var frontierNodes: [KnowledgeMapNode] = []
        var frontierLinks: [KnowledgeMapLink] = []

        for source in exploredTopics.suffix(4) {
            let sourceEdges = graph.edges
                .filter { edge in
                    edge.from == source.id
                        && !exploredIds.contains(edge.to)
                        && edge.generationStatus != .failed
                        && graphTopics[edge.to] != nil
                }
                .sorted { lhs, rhs in
                    let leftRank = lhs.rank ?? Int.max
                    let rightRank = rhs.rank ?? Int.max
                    if leftRank == rightRank {
                        return lhs.strength > rhs.strength
                    }
                    return leftRank < rightRank
                }
                .prefix(3)

            for edge in sourceEdges where frontierIds.count < 12 {
                guard !frontierIds.contains(edge.to),
                      let topic = graphTopics[edge.to],
                      let sourcePosition = exploredNodePositions[source.id]
                else { continue }

                frontierIds.insert(edge.to)
                let position = frontierPosition(
                    sourcePosition: sourcePosition,
                    edge: edge,
                    ordinal: frontierIds.count - 1,
                    size: safeSize
                )
                let node = KnowledgeMapNode(
                    id: edge.to,
                    topic: topic,
                    title: topic.title,
                    pillar: topic.pillar,
                    position: position,
                    kind: .frontier
                )
                frontierNodes.append(node)
                frontierLinks.append(
                    KnowledgeMapLink(
                        id: edge.id,
                        from: sourcePosition,
                        to: position,
                        edgeType: edge.type,
                        isFrontier: true
                    )
                )
            }
        }

        nodes.append(contentsOf: frontierNodes)
        links.append(contentsOf: frontierLinks)

        return KnowledgeMapLayout(
            nodes: nodes,
            links: links,
            frontierCount: frontierNodes.count,
            accessibleCount: frontierNodes.count
        )
    }

    private static func focusedLayout(
        topic: Topic,
        exploredTopics: [Topic],
        exploredIds: Set<String>,
        graph: WikisGraph?,
        graphTopics: [String: Topic],
        size: CGSize
    ) -> KnowledgeMapLayout {
        let center = CGPoint(x: size.width * 0.5, y: size.height * 0.46)
        let focusKind: KnowledgeMapNodeKind = if topic.id == exploredTopics.last?.id {
            .current
        } else if exploredIds.contains(topic.id) {
            .explored
        } else {
            .frontier
        }
        var nodes = [
            KnowledgeMapNode(
                id: topic.id,
                topic: topic,
                title: topic.title,
                pillar: topic.pillar,
                position: center,
                kind: focusKind
            )
        ]
        var links: [KnowledgeMapLink] = []

        guard let graph else {
            return KnowledgeMapLayout(nodes: nodes, links: links, frontierCount: 0, accessibleCount: 0)
        }

        let sourceEdges = graph.edges
            .filter { edge in
                edge.from == topic.id
                    && edge.to != topic.id
                    && edge.generationStatus != .failed
                    && graphTopics[edge.to] != nil
            }
            .sorted { lhs, rhs in
                let leftRank = lhs.rank ?? Int.max
                let rightRank = rhs.rank ?? Int.max
                if leftRank == rightRank {
                    return lhs.strength > rhs.strength
                }
                return leftRank < rightRank
            }
            .prefix(8)

        for (index, edge) in sourceEdges.enumerated() {
            guard let target = graphTopics[edge.to] else { continue }
            let targetKind: KnowledgeMapNodeKind = if target.id == exploredTopics.last?.id {
                .current
            } else if exploredIds.contains(target.id) {
                .explored
            } else {
                .frontier
            }
            let position = focusedNeighborPosition(index: index, count: sourceEdges.count, size: size)
            nodes.append(
                KnowledgeMapNode(
                    id: target.id,
                    topic: target,
                    title: target.title,
                    pillar: target.pillar,
                    position: position,
                    kind: targetKind
                )
            )
            links.append(
                KnowledgeMapLink(
                    id: edge.id,
                    from: center,
                    to: position,
                    edgeType: edge.type,
                    isFrontier: targetKind == .frontier
                )
            )
        }

        let contextTopics = exploredTopics
            .suffix(5)
            .filter { contextTopic in
                contextTopic.id != topic.id && !nodes.contains { $0.id == contextTopic.id }
            }
        for (index, contextTopic) in contextTopics.enumerated() {
            let position = routeContextPosition(index: index, count: contextTopics.count, size: size)
            nodes.append(
                KnowledgeMapNode(
                    id: contextTopic.id,
                    topic: contextTopic,
                    title: contextTopic.title,
                    pillar: contextTopic.pillar,
                    position: position,
                    kind: .explored
                )
            )
            links.append(
                KnowledgeMapLink(
                    id: "\(topic.id)-context-\(contextTopic.id)",
                    from: center,
                    to: position,
                    edgeType: .teleport,
                    isFrontier: true
                )
            )
        }

        return KnowledgeMapLayout(
            nodes: nodes,
            links: links,
            frontierCount: nodes.filter(\.isFrontier).count,
            accessibleCount: sourceEdges.count
        )
    }

    private static func exploredPosition(index: Int, count: Int, size: CGSize) -> CGPoint {
        let center = CGPoint(x: size.width * 0.5, y: size.height * 0.52)
        guard index > 0 else { return center }

        let shortestSide = min(size.width, size.height)
        let stepRadius = min(shortestSide * 0.105, CGFloat(50))
        let radius = min(CGFloat(index) * stepRadius, shortestSide * 0.37)
        let angle = -CGFloat.pi / 2 + CGFloat(index) * 0.86
        let point = CGPoint(
            x: center.x + cos(angle) * radius,
            y: center.y + sin(angle) * radius * 0.78
        )
        return clamped(point, in: size, margin: 72)
    }

    private static func frontierPosition(sourcePosition: CGPoint, edge: TopicEdge, ordinal: Int, size: CGSize) -> CGPoint {
        let baseAngle: CGFloat
        switch edge.type {
        case .deeper, .prerequisite:
            baseAngle = -CGFloat.pi / 2
        case .neighbor, .contrast, .person, .place:
            baseAngle = 0
        case .teleport:
            baseAngle = CGFloat.pi
        }
        let rank = CGFloat(edge.rank ?? ordinal)
        let spread = (rank - 1) * 0.42 + CGFloat(ordinal % 3) * 0.18
        let distance = CGFloat(72 + min(ordinal, 5) * 9)
        let point = CGPoint(
            x: sourcePosition.x + cos(baseAngle + spread) * distance,
            y: sourcePosition.y + sin(baseAngle + spread) * distance * 0.82
        )
        return clamped(point, in: size, margin: 56)
    }

    private static func focusedNeighborPosition(index: Int, count: Int, size: CGSize) -> CGPoint {
        let center = CGPoint(x: size.width * 0.5, y: size.height * 0.46)
        let radius = min(min(size.width, size.height) * 0.31, CGFloat(126))
        let angle = -CGFloat.pi / 2 + CGFloat(index) / CGFloat(max(count, 1)) * CGFloat.pi * 2
        let point = CGPoint(
            x: center.x + cos(angle) * radius,
            y: center.y + sin(angle) * radius * 0.78
        )
        return clamped(point, in: size, margin: 58)
    }

    private static func routeContextPosition(index: Int, count: Int, size: CGSize) -> CGPoint {
        let availableWidth = size.width - 116
        let x = 58 + availableWidth * (CGFloat(index) + 0.5) / CGFloat(max(count, 1))
        let y = min(size.height - 220, size.height * 0.67)
        return clamped(CGPoint(x: x, y: y), in: size, margin: 58)
    }

    private static func clamped(_ point: CGPoint, in size: CGSize, margin: CGFloat) -> CGPoint {
        CGPoint(
            x: min(max(point.x, margin), max(margin, size.width - margin)),
            y: min(max(point.y, margin + 96), max(margin, size.height - margin - 72))
        )
    }
}

private struct KnowledgeMapNode: Identifiable {
    let id: String
    let topic: Topic
    let title: String
    let pillar: Pillar
    let position: CGPoint
    let kind: KnowledgeMapNodeKind

    var isCurrent: Bool {
        kind == .current
    }

    var isFrontier: Bool {
        kind == .frontier
    }

    var diameter: CGFloat {
        switch kind {
        case .current: 24
        case .explored: 17
        case .frontier: 9
        }
    }

    var fill: Color {
        switch kind {
        case .current: .wikisGold
        case .explored: pillar.accentColor
        case .frontier: .white.opacity(0.22)
        }
    }

    var stroke: Color {
        switch kind {
        case .current: .white.opacity(0.86)
        case .explored: .white.opacity(0.54)
        case .frontier: .white.opacity(0.28)
        }
    }

    var glow: Color {
        switch kind {
        case .current: .wikisGold.opacity(0.42)
        case .explored: pillar.accentColor.opacity(0.26)
        case .frontier: .clear
        }
    }

    var accessibilityLabel: String {
        switch kind {
        case .current:
            "Current topic, \(title)"
        case .explored:
            "Explored topic, \(title)"
        case .frontier:
            "Nearby unrevealed topic, \(title)"
        }
    }
}

private enum KnowledgeMapNodeKind {
    case explored
    case current
    case frontier
}

private struct KnowledgeMapLink: Identifiable {
    let id: String
    let from: CGPoint
    let to: CGPoint
    let edgeType: EdgeType
    let isFrontier: Bool

    var color: Color {
        if !isFrontier {
            return .wikisGold
        }

        switch edgeType {
        case .deeper, .prerequisite:
            return .wikisCream
        case .neighbor, .contrast, .person, .place:
            return .wikisBlue
        case .teleport:
            return .wikisViolet
        }
    }
}
