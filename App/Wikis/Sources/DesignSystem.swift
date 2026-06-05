import SwiftUI
#if canImport(WikisCore)
import WikisCore
#endif

extension Color {
    static let wikisInk = Color(red: 0.018, green: 0.039, blue: 0.070)
    static let wikisCream = Color(red: 0.965, green: 0.940, blue: 0.875)
    static let wikisGold = Color(red: 1.000, green: 0.760, blue: 0.180)
    static let wikisViolet = Color(red: 0.510, green: 0.350, blue: 0.960)
    static let wikisCoral = Color(red: 0.930, green: 0.310, blue: 0.330)
    static let wikisBlue = Color(red: 0.270, green: 0.500, blue: 0.920)
}

extension Pillar {
    var accentColor: Color {
        switch self {
        case .science: .wikisGold
        case .literature: .wikisViolet
        case .society: .wikisCoral
        case .history: .wikisBlue
        }
    }

    var symbolName: String {
        switch self {
        case .science: "atom"
        case .literature: "book.closed"
        case .society: "person.2"
        case .history: "building.columns"
        }
    }

    var backgroundGradient: LinearGradient {
        switch self {
        case .science:
            LinearGradient(colors: [.wikisInk, Color(red: 0.05, green: 0.08, blue: 0.13), .black], startPoint: .topLeading, endPoint: .bottomTrailing)
        case .literature:
            LinearGradient(colors: [.wikisInk, Color(red: 0.10, green: 0.06, blue: 0.15), .black], startPoint: .topLeading, endPoint: .bottomTrailing)
        case .society:
            LinearGradient(colors: [.wikisInk, Color(red: 0.13, green: 0.05, blue: 0.06), .black], startPoint: .topLeading, endPoint: .bottomTrailing)
        case .history:
            LinearGradient(colors: [.wikisInk, Color(red: 0.07, green: 0.08, blue: 0.12), .black], startPoint: .topLeading, endPoint: .bottomTrailing)
        }
    }
}
