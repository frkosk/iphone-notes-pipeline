// voz-cli — thin CLI wrapper around Desert Ant Labs' Voz speech transcription.
// Usage: voz-cli <path/to/audio>
// Output (stdout): JSON { "text", "words": [{start,end,text}], "duration_s", "processing_s" }
// Errors to stderr, non-zero exit code.

import Foundation
import Voz
import AudioIO

struct WordOut: Codable {
    let start: Double
    let end: Double
    let text: String
}

struct TranscribeOut: Codable {
    let text: String
    let words: [WordOut]
    let duration_s: Double
    let processing_s: Double
    let realtime_factor: Double
}

@main
struct App {
    static func main() async {
        let args = CommandLine.arguments
        guard args.count >= 2 else {
            FileHandle.standardError.write("usage: voz-cli <audio>\n".data(using: .utf8)!)
            exit(2)
        }
        let path = args[1]

        guard FileManager.default.fileExists(atPath: path) else {
            FileHandle.standardError.write("file not found: \(path)\n".data(using: .utf8)!)
            exit(3)
        }

        do {
            // 1. Decode audio to 16 kHz mono Float samples (via AudioIO helper).
            let samples = try await AudioIO.decode(path: path, sampleRate: 16000)

            // 2. Initialize Voz (first run downloads model to default cache dir).
            let voz = try await Voz()

            // 3. Transcribe.
            let result = try await voz.transcribe(samples: samples)

            // 4. Build JSON output.
            let words = result.words.map {
                WordOut(start: $0.start, end: $0.end, text: $0.text)
            }
            let out = TranscribeOut(
                text: result.text,
                words: words,
                duration_s: result.duration,
                processing_s: result.processingTime,
                realtime_factor: result.realtimeFactor
            )

            let encoder = JSONEncoder()
            encoder.outputFormatting = [.sortedKeys]
            let data = try encoder.encode(out)
            FileHandle.standardOutput.write(data)
            FileHandle.standardOutput.write("\n".data(using: .utf8)!)
        } catch {
            FileHandle.standardError.write("transcribe failed: \(error)\n".data(using: .utf8)!)
            exit(4)
        }
    }
}
