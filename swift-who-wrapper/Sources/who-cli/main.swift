// who-cli — thin CLI wrapper around Desert Ant Labs' Who speaker diarization.
// Usage: who-cli <path/to/audio> [--min-share FRACTION]
//   --min-share 0.05  → drop speakers that occupy < 5% of total audio time
// Output (stdout): JSON { "speakers": N, "turns": [...], "elapsed_s": X }
// Errors to stderr, non-zero exit code.

import Foundation
import Who

struct TurnOut: Codable {
    let start: Double
    let end: Double
    let speaker: String
}

struct DiarizeOut: Codable {
    let speakers: Int
    let turns: [TurnOut]
    let elapsed_s: Double
}

@main
struct App {
    static func main() async {
        let args = CommandLine.arguments
        guard args.count >= 2 else {
            FileHandle.standardError.write("usage: who-cli <audio> [--min-share FRACTION]\n".data(using: .utf8)!)
            exit(2)
        }
        let path = args[1]
        let url = URL(fileURLWithPath: path)

        var minShare: Double? = nil
        if let i = args.firstIndex(of: "--min-share"), i + 1 < args.count,
           let v = Double(args[i + 1]) {
            minShare = v
        }

        guard FileManager.default.fileExists(atPath: path) else {
            FileHandle.standardError.write("file not found: \(path)\n".data(using: .utf8)!)
            exit(3)
        }

        do {
            let t0 = Date()
            let who = Who()
            var result = try await who.diarize(contentsOf: url)
            if let s = minShare {
                result = result.keepingSpeakers(minimumShare: s)
            }
            let elapsed = Date().timeIntervalSince(t0)

            let turns = result.turns.map { t in
                TurnOut(
                    start: t.start,
                    end: t.end,
                    speaker: String(format: "SPEAKER_%02d", t.speaker)
                )
            }
            let out = DiarizeOut(
                speakers: result.speakerCount,
                turns: turns,
                elapsed_s: elapsed
            )

            let encoder = JSONEncoder()
            encoder.outputFormatting = [.sortedKeys]
            let data = try encoder.encode(out)
            FileHandle.standardOutput.write(data)
            FileHandle.standardOutput.write("\n".data(using: .utf8)!)
        } catch {
            FileHandle.standardError.write("diarize failed: \(error)\n".data(using: .utf8)!)
            exit(4)
        }
    }
}
