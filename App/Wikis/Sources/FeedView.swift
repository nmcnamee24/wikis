import SwiftUI
#if canImport(WikisCore)
import WikisCore
#endif

struct FeedView: View {
    @ObservedObject var store: FeedStore
    @GestureState private var dragOffset: CGSize = .zero
    @State private var exitOffset: CGSize = .zero
    @State private var isTransitioning = false

    var body: some View {
        ZStack {
            if let topic = store.currentTopic {
                let cardOffset = isTransitioning ? .zero : visualOffset(for: dragOffset)
                let combinedOffset = CGSize(
                    width: cardOffset.width + exitOffset.width,
                    height: cardOffset.height + exitOffset.height
                )

                TopicCardView(
                    topic: topic,
                    isSaved: store.isSaved(topic),
                    dragOffset: cardOffset,
                    onSave: store.toggleSaveCurrentTopic,
                    onContinue: { store.navigate(.down) },
                    onBack: store.goBack
                )
                .scaleEffect(scale(for: combinedOffset))
                .rotationEffect(.degrees(rotation(for: combinedOffset)))
                .offset(combinedOffset)
                .opacity(opacity(for: combinedOffset))
                .simultaneousGesture(
                    DragGesture(minimumDistance: 24)
                        .updating($dragOffset) { value, state, _ in
                            state = isHorizontalIntent(value.translation) ? value.translation : .zero
                        }
                        .onEnded { value in
                            guard !isTransitioning else { return }
                            let gesture = resolvedGesture(from: value)
                            if let gesture {
                                navigateWithSwipe(gesture, from: visualOffset(for: value.translation))
                            }
                        }
                )
                .id(topic.id)
                .transition(.opacity.combined(with: .scale(scale: 0.98)))
            } else {
                VStack(spacing: 12) {
                    ProgressView()
                    Text(store.loadingError ?? "Loading Wikis")
                        .font(.headline)
                        .foregroundStyle(Color.white.opacity(0.8))
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.wikisInk)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .clipped()
        .ignoresSafeArea()
    }

    private func visualOffset(for translation: CGSize) -> CGSize {
        guard isHorizontalIntent(translation) else { return .zero }
        return CGSize(
            width: translation.width * 0.46,
            height: translation.height * 0.08
        )
    }

    private func isHorizontalIntent(_ translation: CGSize) -> Bool {
        let horizontal = abs(translation.width)
        let vertical = abs(translation.height)
        return horizontal > 18 && horizontal > vertical * 1.12
    }

    private func resolvedGesture(from value: DragGesture.Value) -> NavigationGesture? {
        let translation = value.translation
        let projected = value.predictedEndTranslation
        let horizontal = translation.width
        let vertical = translation.height
        let projectedHorizontal = projected.width
        let projectedVertical = projected.height

        let axisIsClear = abs(horizontal) > abs(vertical) * 1.12
            && abs(projectedHorizontal) > abs(projectedVertical) * 1.08
        let distanceIsEnough = abs(horizontal) > 78
        let flickIsEnough = abs(horizontal) > 32 && abs(projectedHorizontal) > 128

        guard axisIsClear && (distanceIsEnough || flickIsEnough) else {
            return nil
        }

        let direction = abs(projectedHorizontal) > abs(horizontal) ? projectedHorizontal : horizontal
        if direction > 0 {
            return .left
        }
        if direction < 0 {
            return .right
        }
        return nil
    }

    private func navigateWithSwipe(_ gesture: NavigationGesture, from releaseOffset: CGSize) {
        let direction: CGFloat = {
            switch gesture {
            case .left: 1
            case .right: -1
            case .down: 0
            }
        }()

        var transaction = Transaction()
        transaction.disablesAnimations = true
        withTransaction(transaction) {
            exitOffset = releaseOffset
            isTransitioning = true
        }

        DispatchQueue.main.async {
            withAnimation(.spring(response: 0.34, dampingFraction: 0.82)) {
                exitOffset = CGSize(
                    width: releaseOffset.width + direction * 620,
                    height: releaseOffset.height - 18
                )
            }
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.16) {
            store.navigate(gesture)
            var resetTransaction = Transaction()
            resetTransaction.disablesAnimations = true
            withTransaction(resetTransaction) {
                exitOffset = .zero
                isTransitioning = false
            }
        }
    }

    private func rotation(for offset: CGSize) -> Double {
        Double(min(max(offset.width / 34, -10), 10))
    }

    private func scale(for offset: CGSize) -> CGFloat {
        1 - min(abs(offset.width) / 2600, 0.045)
    }

    private func opacity(for offset: CGSize) -> Double {
        1 - min(abs(offset.width) / 900, 0.32)
    }
}
