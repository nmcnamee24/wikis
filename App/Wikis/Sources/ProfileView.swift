import SwiftUI
#if canImport(WikisCore)
import WikisCore
#endif

struct ProfileView: View {
    @ObservedObject var store: FeedStore

    var body: some View {
        NavigationStack {
            ZStack {
                Color.wikisInk.ignoresSafeArea()

                VStack(alignment: .leading, spacing: 24) {
                    Text("Profile")
                        .font(.system(size: 30, weight: .bold))
                        .foregroundStyle(Color.wikisCream)

                    HStack(spacing: 14) {
                        ProfileMetric(title: "Topics", value: "\(store.exploredTopics.count)")
                        ProfileMetric(title: "Saved", value: "\(store.savedTopicIds.count)")
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        Text("Pillar Mix")
                            .font(.system(size: 18, weight: .bold))
                            .foregroundStyle(Color.wikisCream)

                        ForEach(Pillar.allCases, id: \.self) { pillar in
                            let count = store.exploredTopics.filter { $0.pillar == pillar }.count
                            HStack {
                                Label(pillar.displayName, systemImage: pillar.symbolName)
                                    .foregroundStyle(pillar.accentColor)
                                Spacer()
                                Text("\(count)")
                                    .foregroundStyle(Color.white.opacity(0.78))
                            }
                            .font(.system(size: 16, weight: .medium))
                        }
                    }
                    .padding(18)
                    .background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 8))

                    Spacer()
                }
                .padding(20)
            }
        }
    }
}

private struct ProfileMetric: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(value)
                .font(.system(size: 26, weight: .bold))
                .foregroundStyle(Color.wikisCream)
            Text(title)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(Color.white.opacity(0.58))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(.white.opacity(0.055), in: RoundedRectangle(cornerRadius: 8))
    }
}
