import SwiftUI
#if canImport(WikisCore)
import WikisCore
#endif

struct TopicCardView: View {
    let topic: Topic
    let isSaved: Bool
    let dragOffset: CGSize
    let onSave: () -> Void
    let onContinue: () -> Bool
    let onBack: () -> Bool

    @GestureState private var verticalDragTranslation: CGSize = .zero
    @State private var scrollOffset: CGFloat = 0
    @State private var scrollViewportHeight: CGFloat = 0
    @State private var scrollContentHeight: CGFloat = 0
    @State private var verticalExitOffset: CGFloat = 0
    @State private var isVerticalTransitioning = false

    var body: some View {
        let activeVerticalOffset = isVerticalTransitioning ? verticalExitOffset : verticalVisualOffset(for: verticalDragTranslation)

        ZStack(alignment: .top) {
            TopicBackground(topic: topic)
                .clipped()

            LinearGradient(
                colors: [
                    .black.opacity(0.30),
                    .wikisInk.opacity(0.84),
                    .wikisInk.opacity(0.97)
                ],
                startPoint: .top,
                endPoint: .bottom
            )

            VStack(alignment: .leading, spacing: 0) {
                header
                    .frame(maxWidth: .infinity, alignment: .leading)

                ScrollView(showsIndicators: false) {
                    VStack(alignment: .leading, spacing: 0) {
                        GeometryReader { proxy in
                            Color.clear
                                .preference(
                                    key: ScrollOffsetPreferenceKey.self,
                                    value: proxy.frame(in: .named(scrollCoordinateSpace)).minY
                                )
                        }
                        .frame(height: 0)

                        Text(topic.title)
                            .font(.system(size: titleSize, weight: .bold, design: .default))
                            .lineLimit(4)
                            .minimumScaleFactor(0.58)
                            .multilineTextAlignment(.leading)
                            .foregroundStyle(Color.wikisCream)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.bottom, 18)

                        Rectangle()
                            .fill(topic.pillar.accentColor)
                            .frame(width: 62, height: 3)
                            .padding(.bottom, 28)

                        Text(topic.explanation)
                            .font(.system(size: bodySize, weight: .regular))
                            .lineSpacing(7)
                            .multilineTextAlignment(.leading)
                            .foregroundStyle(Color.white.opacity(0.92))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.bottom, 42)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background {
                        GeometryReader { proxy in
                            Color.clear
                                .preference(key: ScrollContentHeightPreferenceKey.self, value: proxy.size.height)
                        }
                    }
                }
                .coordinateSpace(name: scrollCoordinateSpace)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                .background {
                    GeometryReader { proxy in
                        Color.clear
                            .preference(key: ScrollViewportHeightPreferenceKey.self, value: proxy.size.height)
                    }
                }
                .simultaneousGesture(verticalNavigationGesture)

                Spacer(minLength: 72)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .padding(.horizontal, 24)
            .padding(.top, 58)
            .padding(.bottom, 24)
            .offset(y: activeVerticalOffset)
            .scaleEffect(verticalScale(for: activeVerticalOffset))
            .opacity(verticalOpacity(for: activeVerticalOffset))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .clipped()
        .onPreferenceChange(ScrollOffsetPreferenceKey.self) { scrollOffset = $0 }
        .onPreferenceChange(ScrollViewportHeightPreferenceKey.self) { scrollViewportHeight = $0 }
        .onPreferenceChange(ScrollContentHeightPreferenceKey.self) { scrollContentHeight = $0 }
        .overlay(alignment: .bottom) {
            gestureHint
                .padding(.bottom, 86)
        }
    }

    private let scrollCoordinateSpace = "TopicCardScroll"

    private var titleSize: CGFloat {
        if topic.title.count > 34 {
            return 45
        }
        if topic.title.count > 22 {
            return 50
        }
        return 58
    }

    private var bodySize: CGFloat {
        topic.explanation.count > 430 ? 18 : 20
    }

    private var header: some View {
        HStack(spacing: 12) {
            Label(topic.pillar.displayName, systemImage: topic.pillar.symbolName)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(topic.pillar.accentColor)
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(.black.opacity(0.28), in: Capsule())

            Spacer()

            Button(action: onSave) {
                Image(systemName: isSaved ? "bookmark.fill" : "bookmark")
                    .font(.system(size: 18, weight: .medium))
                    .frame(width: 42, height: 42)
                    .background(.black.opacity(0.24), in: Circle())
                    .foregroundStyle(isSaved ? Color.wikisGold : Color.white)
            }
            .accessibilityLabel(isSaved ? "Unsave topic" : "Save topic")

            Button(action: {}) {
                Image(systemName: "ellipsis")
                    .font(.system(size: 18, weight: .medium))
                    .frame(width: 42, height: 42)
                    .background(.black.opacity(0.24), in: Circle())
                    .foregroundStyle(Color.white)
            }
            .accessibilityLabel("More options")
        }
    }

    private var gestureHint: some View {
        let hintOffset = CGSize(
            width: dragOffset.width,
            height: dragOffset.height + verticalVisualOffset(for: verticalDragTranslation)
        )
        let label: String? = {
            if hintOffset.height < -50, abs(hintOffset.height) > abs(hintOffset.width) {
                return "Continue"
            }
            if hintOffset.width > 50, abs(hintOffset.width) > abs(hintOffset.height) {
                return "Random"
            }
            if hintOffset.width < -50, abs(hintOffset.width) > abs(hintOffset.height) {
                return "Explore"
            }
            if hintOffset.height > 50, abs(hintOffset.height) > abs(hintOffset.width) {
                return "Back"
            }
            return nil
        }()

        return Group {
            if let label {
                Text(label)
                    .font(.system(size: 13, weight: .bold))
                    .textCase(.uppercase)
                    .foregroundStyle(Color.wikisCream)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 9)
                    .background(.black.opacity(0.36), in: Capsule())
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var verticalNavigationGesture: some Gesture {
        DragGesture(minimumDistance: 34)
            .updating($verticalDragTranslation) { value, state, _ in
                guard isBoundaryPull(value.translation) else { return }
                state = value.translation
            }
            .onEnded { value in
                guard !isVerticalTransitioning, let direction = resolvedVerticalNavigation(from: value) else {
                    return
                }
                navigateVertically(direction, from: verticalVisualOffset(for: value.translation))
            }
    }

    private func isVerticalNavigation(_ value: DragGesture.Value, direction: VerticalNavigationDirection) -> Bool {
        let vertical = value.translation.height
        let horizontal = value.translation.width
        let projectedVertical = value.predictedEndTranslation.height
        let projectedHorizontal = value.predictedEndTranslation.width

        let isCorrectDirection = direction == .down ? vertical > 0 : vertical < 0
        let axisIsClear = abs(vertical) > abs(horizontal) * 1.55
            && abs(projectedVertical) > abs(projectedHorizontal) * 1.25
        let distanceIsEnough = abs(vertical) > 132
        let flickIsEnough = abs(vertical) > 62 && abs(projectedVertical) > 220

        return isCorrectDirection && axisIsClear && (distanceIsEnough || flickIsEnough)
    }

    private func isBoundaryPull(_ translation: CGSize) -> Bool {
        let vertical = translation.height
        let horizontal = abs(translation.width)
        guard abs(vertical) > 28, abs(vertical) > horizontal * 1.35 else {
            return false
        }
        return vertical > 0 ? isAtTop : isAtBottom
    }

    private func resolvedVerticalNavigation(from value: DragGesture.Value) -> VerticalNavigationDirection? {
        if isVerticalNavigation(value, direction: .down), isAtTop {
            return .down
        }
        if isVerticalNavigation(value, direction: .up), isAtBottom {
            return .up
        }
        return nil
    }

    private var isAtTop: Bool {
        scrollOffset >= -8
    }

    private var isAtBottom: Bool {
        guard maxScrollableDistance > 12 else { return true }
        return -scrollOffset >= maxScrollableDistance - 18
    }

    private var maxScrollableDistance: CGFloat {
        max(scrollContentHeight - scrollViewportHeight, 0)
    }

    private func verticalVisualOffset(for translation: CGSize) -> CGFloat {
        guard isBoundaryPull(translation) else { return 0 }
        return translation.height * 0.34
    }

    private func navigateVertically(_ direction: VerticalNavigationDirection, from releaseOffset: CGFloat) {
        let exitDirection: CGFloat = direction == .up ? -1 : 1

        var transaction = Transaction()
        transaction.disablesAnimations = true
        withTransaction(transaction) {
            verticalExitOffset = releaseOffset
            isVerticalTransitioning = true
        }

        DispatchQueue.main.async {
            withAnimation(.spring(response: 0.36, dampingFraction: 0.84)) {
                verticalExitOffset = releaseOffset + exitDirection * 680
            }
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.18) {
            let didNavigate = switch direction {
            case .up:
                onContinue()
            case .down:
                onBack()
            }

            guard !didNavigate else { return }

            var resetTransaction = Transaction()
            resetTransaction.disablesAnimations = true
            withTransaction(resetTransaction) {
                verticalExitOffset = 0
                isVerticalTransitioning = false
            }
        }
    }

    private func verticalScale(for offset: CGFloat) -> CGFloat {
        1 - min(abs(offset) / 3600, 0.035)
    }

    private func verticalOpacity(for offset: CGFloat) -> Double {
        1 - min(abs(offset) / 1000, 0.24)
    }
}

private enum VerticalNavigationDirection {
    case up
    case down
}

private struct ScrollOffsetPreferenceKey: PreferenceKey {
    static let defaultValue: CGFloat = 0

    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = nextValue()
    }
}

private struct ScrollViewportHeightPreferenceKey: PreferenceKey {
    static let defaultValue: CGFloat = 0

    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = nextValue()
    }
}

private struct ScrollContentHeightPreferenceKey: PreferenceKey {
    static let defaultValue: CGFloat = 0

    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) {
        value = nextValue()
    }
}

private struct TopicBackground: View {
    let topic: Topic

    var body: some View {
        GeometryReader { proxy in
            ZStack {
                topic.pillar.backgroundGradient

                if let url = topic.image.selected?.thumbnailUrl ?? topic.image.selected?.url {
                    AsyncImage(url: url) { phase in
                        switch phase {
                        case .success(let image):
                            image
                                .resizable()
                                .scaledToFill()
                                .frame(width: proxy.size.width, height: proxy.size.height)
                                .clipped()
                                .opacity(0.58)
                        case .empty:
                            topic.pillar.backgroundGradient
                        case .failure:
                            topic.pillar.backgroundGradient
                        @unknown default:
                            topic.pillar.backgroundGradient
                        }
                    }
                }
            }
            .frame(width: proxy.size.width, height: proxy.size.height)
            .clipped()
        }
        .ignoresSafeArea()
    }
}
