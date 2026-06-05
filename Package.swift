// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "Wikis",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    products: [
        .library(name: "WikisCore", targets: ["WikisCore"]),
        .executable(name: "WikisPrototype", targets: ["WikisPrototype"]),
        .executable(name: "WikisCoreSmokeTests", targets: ["WikisCoreSmokeTests"])
    ],
    targets: [
        .target(name: "WikisCore"),
        .executableTarget(
            name: "WikisPrototype",
            dependencies: ["WikisCore"],
            path: "App/Wikis",
            sources: ["Sources"],
            resources: [
                .copy("Resources/seed_graph.json")
            ]
        ),
        .executableTarget(name: "WikisCoreSmokeTests", dependencies: ["WikisCore"])
    ]
)
