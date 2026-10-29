"""Directory sweep: find new .m4a files, stability check, dedup, process serially."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from .config import Config
from .pipeline import process_file


log = logging.getLogger("meet_transcriber.watcher")

STABILITY_WAIT_S = 10
VALID_SUFFIX = {".m4a", ".mp3", ".wav", ".mp4", ".m4v"}


def _is_candidate(p: Path) -> bool:
    if not p.is_file():
        return False
    if p.suffix.lower() not in VALID_SUFFIX:
        return False
    if p.name.startswith("."):  # .icloud placeholders
        return False
    return True


def _is_stable(p: Path, wait_s: int = STABILITY_WAIT_S) -> bool:
    try:
        age = time.time() - p.stat().st_mtime
        return age >= wait_s
    except FileNotFoundError:
        return False


def sweep(cfg: Config, templates_dir: Path) -> int:
    """Scan source folder, process new stable files. Returns count processed."""
    source = cfg.source_path
    if not source.is_dir():
        log.error(f"source folder missing: {source}")
        return 0

    count = 0
    for p in sorted(source.iterdir()):
        if not _is_candidate(p):
            continue
        if not _is_stable(p):
            log.debug(f"not stable yet: {p.name}")
            continue
        try:
            result = process_file(p, cfg, templates_dir)
            if result:
                count += 1
        except Exception as e:
            log.exception(f"failed to process {p.name}: {e}")
    return count
