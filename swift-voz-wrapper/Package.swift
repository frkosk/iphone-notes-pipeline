// swift-tools-version:6.0
import PackageDescription

let package = Package(
    name: "voz-cli",
    platforms: [
        .macOS(.v15),
    ],
    products: [
        .executable(name: "voz-cli", targets: ["voz-cli"]),
    ],
    dependencies: [
        .package(url: "https://github.com/Desert-Ant-Labs/desert-ant-core.git", from: "4.0.0"),
    ],
    targets: [
        .executableTarget(
            name: "voz-cli",
            dependencies: [
                .product(name: "Voz", package: "desert-ant-core"),
                .product(name: "AudioIO", package: "desert-ant-core"),
            ],
            path: "Sources/voz-cli"
        ),
    ]
)
