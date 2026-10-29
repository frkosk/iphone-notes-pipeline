"""Speaker diarization via Desert Ant Labs' Who (Swift CLI wrapper).

The actual diarization is a native Swift binary built from `swift-who-wrapper/`.
This module just shells out to it and parses JSON.

~200-300× real-time on Apple Silicon. No HF token, no PyTorch, no model-download
dance for the user — the Who SDK handles its own model fetching on first run.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


log = logging.getLogger("meet_transcriber.diarize")


# Drop speakers whose cumulative talk-time is below this (absolute seconds).
# Scales naturally with recording length: a monologue's artefact-speakers under
# ~10s get purged, while real but minor contributors in a long meeting (say,
# someone who only chimes in for 20-30s in a 60-min call) pass through.
# Calibrated for client meetings; tweak here if use case shifts.
MIN_SECONDS = 10.0


@dataclass
class Turn:
    start: float
    end: float
    speaker: str  # "SPEAKER_00" etc


def _find_cli() -> Path:
    """Locate the who-cli binary.
    - Packaged .pkg install:  /usr/local/opt/meet-transcriber/bin/who-cli
    - Dev symlink:            /usr/local/opt/meet-transcriber/bin/who-cli (same)
    - Repo build:             <repo>/swift-who-wrapper/.build/release/who-cli
    """
    env = os.environ.get("MEET_TRANSCRIBER_WHO_CLI")
    if env:
        return Path(env)

    pkg = Path("/usr/local/opt/meet-transcriber/bin/who-cli")
    if pkg.exists():
        return pkg

    # dev: repo-local build
    here = Path(__file__).resolve()
    repo_root = here.parents[2]   # src/meet_transcriber/diarize.py → src → repo
    dev = repo_root / "swift-who-wrapper/.build/release/who-cli"
    if dev.exists():
        return dev

    raise FileNotFoundError(
        "who-cli not found. Build it with: "
        "`cd swift-who-wrapper && swift build -c release`"
    )


def diarize(wav_path: Path) -> list[Turn]:
    """Return speaker turns for an audio file (WAV/m4a/etc, Who handles decoding)."""
    cli = _find_cli()
    cmd = [str(cli), str(wav_path), "--min-seconds", str(MIN_SECONDS)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"who-cli failed (exit {proc.returncode}): {proc.stderr.strip()[:400]}")

    data = json.loads(proc.stdout)
    turns = [
        Turn(start=float(t["start"]), end=float(t["end"]), speaker=t["speaker"])
        for t in data.get("turns", [])
    ]
    log.info(f"who-cli diarize: {data.get('speakers', '?')} speakers, "
             f"{len(turns)} turns, elapsed={data.get('elapsed_s', 0):.2f}s")
    return turns
