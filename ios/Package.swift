// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "PedalCore",
    platforms: [.iOS(.v17), .macOS(.v13)],
    products: [.library(name: "PedalCore", targets: ["PedalCore"]), .executable(name: "pedal-api-smoke", targets: ["APISmoke"])],
    targets: [
        .target(name: "PedalCore", path: "Sources/PedalCore"),
        .executableTarget(name: "APISmoke", dependencies: ["PedalCore"], path: "Tools/APISmoke"),
        .testTarget(name: "PedalCoreTests", dependencies: ["PedalCore"], path: "Tests/PedalCoreTests")
    ]
)
