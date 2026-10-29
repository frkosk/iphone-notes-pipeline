"""Orchestrator: audio file → transcript → diarize → merge → render → write → notify."""
from __future__ import annotations

import logging
import re
import tempfile
from datetime import datetime
from pathlib import Path


_VM_NAME_RE = re.compile(r"^(\d{8})\s+(\d{6})[-.]")


def _parse_recorded_at(path: Path) -> datetime:
    """Voice Memos filename: `YYYYMMDD HHMMSS-GUID.m4a`. Fallback to mtime."""
    m = _VM_NAME_RE.match(path.name)
    if m:
        try:
            return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime)

from . import diarize as diarize_mod
from . import transcribe as transcribe_mod
from .config import Config
from .merge import merge
from .notify import notify
from .output import FolderWriter, ObsidianWriter, RenderInput, render_markdown
from .state import StateDB, fingerprint


log = logging.getLogger("meet_transcriber.pipeline")


def _duration_seconds(wav: Path) -> float:
    import soundfile as sf
    with sf.SoundFile(str(wav)) as f:
        return len(f) / f.samplerate


def process_file(audio_path: Path, cfg: Config, templates_dir: Path, force: bool = False) -> Path | None:
    """Returns output .md path, or None if skipped (dedup)."""
    log.info(f"processing: {audio_path.name}")

    db = StateDB(cfg.db_path)
    fp = fingerprint(audio_path)
    size = audio_path.stat().st_size
    try:
        if not force and db.is_processed(fp):
            log.info(f"skip (already processed): {audio_path.name}")
            return None

        with tempfile.TemporaryDirectory(prefix="meet-transcriber-") as tmp:
            wav = Path(tmp) / "audio.wav"
            transcribe_mod.extract_wav(audio_path, wav)

            # transcribe (Voz via voz-cli)
            transcript = transcribe_mod.transcribe(wav)
            log.info(f"transcribed: {len(transcript.segments)} segments")

            # diarize (Who via who-cli)
            turns = []
            try:
                log.info("diarize start (Who, Desert Ant Labs)")
                turns = diarize_mod.diarize(wav)
                log.info(f"diarized: {len(turns)} turns, {len({t.speaker for t in turns})} speakers")
            except Exception as e:
                log.warning(f"diarization failed, continuing without speakers: {e}")

            labeled = merge(transcript.segments, turns)
            duration = _duration_seconds(wav)

        recorded_at = _parse_recorded_at(audio_path)
        ri = RenderInput(
            source_path=audio_path,
            recorded_at=recorded_at,
            duration_seconds=duration,
            language=transcript.language or "unknown",
            segments=labeled,
        )
        md = render_markdown(ri, templates_dir)

        if cfg.output.mode == "obsidian":
            writer = ObsidianWriter(cfg.output.path, cfg.output.vault_name)
        else:
            writer = FolderWriter(cfg.output.path)

        out_path, uri = writer.write(ri, md)
        log.info(f"written: {out_path}")

        db.mark_processed(fp, audio_path.name, size, str(out_path))

        n_speakers = len({s.speaker for s in labeled if s.speaker != "?"})
        mins = int(duration // 60)
        notify(
            title="Prepis hotový",
            message=f"{recorded_at.strftime('%Y-%m-%d %H:%M')} — {n_speakers} speakers, {mins} min",
            open_url=uri,
        )
        return out_path
    except Exception as e:
        log.exception(f"FAILED {audio_path.name}: {e}")
        db.mark_failed(fp, audio_path.name, size, str(e))
        notify(title="Prepis zlyhal", message=f"{audio_path.name}: {str(e)[:120]}")
        raise
    finally:
        db.close()
