// swift-tools-version:6.0
import PackageDescription

let package = Package(
    name: "who-cli",
    platforms: [
        .macOS(.v15),
    ],
    products: [
        .executable(name: "who-cli", targets: ["who-cli"]),
    ],
    dependencies: [
        .package(url: "https://github.com/Desert-Ant-Labs/desert-ant-core.git", from: "4.0.0"),
    ],
    targets: [
        .executableTarget(
            name: "who-cli",
            dependencies: [
                .product(name: "Who", package: "desert-ant-core"),
            ],
            path: "Sources/who-cli"
        ),
    ]
)
