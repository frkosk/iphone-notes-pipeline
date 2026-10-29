// who-cli — thin CLI wrapper around Desert Ant Labs' Who speaker diarization.
// Usage: who-cli <path/to/audio> [--min-share FRACTION] [--min-seconds N]
//   --min-share 0.05 → drop speakers whose total talk-time is < 5% of audio
//   --min-seconds 10 → drop speakers whose total talk-time is < 10 absolute seconds
//                       (preferred: scales naturally — monologue artefacts under 10s
//                        get purged on short audio; minor-but-real speakers in long
//                        meetings pass through)
// Flags combine (both filters apply if both given).
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

/// Drop turns whose speaker's cumulative talk-time is below `minSeconds`.
/// Then renumber remaining speakers 00, 01, 02... in order of first appearance.
func filterByMinSeconds(_ turns: [(start: Double, end: Double, speaker: Int)],
                        minSeconds: Double) -> [(start: Double, end: Double, speaker: Int)] {
    var talk: [Int: Double] = [:]
    for t in turns {
        talk[t.speaker, default: 0] += (t.end - t.start)
    }
    let keep = Set(talk.filter { $0.value >= minSeconds }.keys)
    let filtered = turns.filter { keep.contains($0.speaker) }

    // Renumber in order of first appearance.
    var mapping: [Int: Int] = [:]
    var next = 0
    for t in filtered.sorted(by: { $0.start < $1.start }) {
        if mapping[t.speaker] == nil {
            mapping[t.speaker] = next
            next += 1
        }
    }
    return filtered.map { (start: $0.start, end: $0.end, speaker: mapping[$0.speaker]!) }
}

@main
struct App {
    static func main() async {
        let args = CommandLine.arguments
        guard args.count >= 2 else {
            FileHandle.standardError.write(
                "usage: who-cli <audio> [--min-share FRACTION] [--min-seconds N]\n".data(using: .utf8)!)
            exit(2)
        }
        let path = args[1]
        let url = URL(fileURLWithPath: path)

        var minShare: Double? = nil
        if let i = args.firstIndex(of: "--min-share"), i + 1 < args.count,
           let v = Double(args[i + 1]) {
            minShare = v
        }
        var minSeconds: Double? = nil
        if let i = args.firstIndex(of: "--min-seconds"), i + 1 < args.count,
           let v = Double(args[i + 1]) {
            minSeconds = v
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

            // Extract turns as plain tuples.
            var tuples: [(start: Double, end: Double, speaker: Int)] = result.turns.map {
                (start: $0.start, end: $0.end, speaker: Int($0.speaker))
            }

            // Apply absolute-seconds filter (if requested).
            if let m = minSeconds {
                tuples = filterByMinSeconds(tuples, minSeconds: m)
            }

            let speakerCount = Set(tuples.map { $0.speaker }).count
            let turns = tuples.map { t in
                TurnOut(start: t.start, end: t.end,
                        speaker: String(format: "SPEAKER_%02d", t.speaker))
            }
            let out = DiarizeOut(
                speakers: speakerCount,
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
