import SwiftUI

struct KnowledgeMapView: View {
    @ObservedObject var store: FeedStore

    var body: some View {
        NavigationStack {
            ZStack {
                Color.wikisInk.ignoresSafeArea()

                VStack(alignment: .leading, spacing: 20) {
                    Text("My Knowledge Map")
                        .font(.system(size: 28, weight: .bold))
                        .foregroundStyle(Color.wikisCream)

                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 12) {
                            ForEach(Array(store.exploredTopics.enumerated()), id: \.offset) { index, topic in
                                HStack(spacing: 12) {
                                    Circle()
                                        .fill(topic.pillar.accentColor)
                                        .frame(width: 10, height: 10)

                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(topic.title)
                                            .font(.system(size: 17, weight: .semibold))
                                            .foregroundStyle(Color.white)
                                        Text(index == 0 ? "Starting point" : "Explored")
                                            .font(.system(size: 13))
                                            .foregroundStyle(Color.white.opacity(0.58))
                                    }

                                    Spacer()
                                }
                                .padding(14)
                                .background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 8))
                            }
                        }
                    }
                }
                .padding(20)
            }
        }
    }
}
