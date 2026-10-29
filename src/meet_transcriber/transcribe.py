"""Speech-to-text via Desert Ant Labs' Voz (Swift CLI wrapper).

Shells out to `voz-cli`, a native Swift binary built from `swift-voz-wrapper/`.
~300-400× real-time on Apple Silicon. No MLX framework, no PyTorch, no HF Hub
dependency. The Voz SDK handles its own model fetching on first run.

ffmpeg is still used for `.m4a → .wav` extraction (pipeline.py expects a wav).
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


log = logging.getLogger("meet_transcriber.transcribe")


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    text: str
    language: str | None
    segments: list[Segment] = field(default_factory=list)


class TranscribeError(RuntimeError):
    pass


def extract_wav(src: Path, dst: Path, sample_rate: int = 16000) -> None:
    """m4a/mp4 → mono 16 kHz WAV. Both voz-cli and who-cli accept the WAV."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(src),
        "-vn", "-ac", "1", "-ar", str(sample_rate),
        "-c:a", "pcm_s16le",
        str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise TranscribeError(f"ffmpeg failed: {proc.stderr.strip()[:500]}")


def _find_cli() -> Path:
    """Locate the voz-cli binary.
    - Packaged .pkg install:  /usr/local/opt/meet-transcriber/bin/voz-cli
    - Repo dev build:         <repo>/swift-voz-wrapper/.build/release/voz-cli
    """
    env = os.environ.get("MEET_TRANSCRIBER_VOZ_CLI")
    if env:
        return Path(env)

    pkg = Path("/usr/local/opt/meet-transcriber/bin/voz-cli")
    if pkg.exists():
        return pkg

    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    dev = repo_root / "swift-voz-wrapper/.build/release/voz-cli"
    if dev.exists():
        return dev

    raise FileNotFoundError(
        "voz-cli not found. Build it with: "
        "`cd swift-voz-wrapper && swift build -c release`"
    )


# Group words into coarse ~5s segments for merge.py — Voz returns word-level
# timestamps, but the pipeline merges against Who speaker turns which are
# naturally segment-sized. 5s is a reasonable chunk.
SEGMENT_WINDOW_S = 5.0


def _words_to_segments(words: list[dict]) -> list[Segment]:
    """Chunk per-word output into fixed-time windows (~5s) with concatenated text."""
    if not words:
        return []
    segments: list[Segment] = []
    cur_start = words[0]["start"]
    cur_end = words[0]["end"]
    cur_text: list[str] = [words[0]["text"]]
    for w in words[1:]:
        if w["start"] - cur_start >= SEGMENT_WINDOW_S:
            segments.append(Segment(start=cur_start, end=cur_end,
                                    text=" ".join(cur_text).strip()))
            cur_start = w["start"]
            cur_text = []
        cur_text.append(w["text"])
        cur_end = w["end"]
    if cur_text:
        segments.append(Segment(start=cur_start, end=cur_end,
                                text=" ".join(cur_text).strip()))
    return segments


def transcribe(audio_path: Path) -> Transcript:
    """Call voz-cli, parse JSON, return Transcript.

    Voz has no per-call model/language/prompt knobs — it uses its single
    Parakeet TDT 0.6B v3 model and auto-detects from the 25 supported EU
    languages. Language is NOT exposed in the current SDK output."""
    cli = _find_cli()
    proc = subprocess.run([str(cli), str(audio_path)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise TranscribeError(
            f"voz-cli failed (exit {proc.returncode}): {proc.stderr.strip()[:400]}"
        )

    data = json.loads(proc.stdout)
    text = (data.get("text") or "").strip()
    words = data.get("words", [])
    segments = _words_to_segments(words)

    duration = data.get("duration_s", 0.0)
    processing = data.get("processing_s", 0.0)
    rtf = data.get("realtime_factor", 0.0)
    log.info(f"voz-cli transcribe: {len(words)} words in {len(segments)} segments, "
             f"processing={processing:.2f}s, {rtf:.1f}x realtime")

    # Voz doesn't expose detected language; we leave it as None so pipeline.py
    # falls back to the Slovak template (our default).
    return Transcript(text=text, language=None, segments=segments)
