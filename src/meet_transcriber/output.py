"""Markdown rendering + Obsidian/Folder writers + Obsidian vault discovery."""
from __future__ import annotations

import json
import os
import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .merge import LabeledSegment


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


@dataclass
class RenderInput:
    source_path: Path
    recorded_at: datetime
    duration_seconds: float
    language: str
    segments: list[LabeledSegment]
    user_name: str = "Ferik"


def render_markdown(ri: RenderInput, templates_dir: Path) -> str:
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(enabled_extensions=(), default=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    tpl = env.get_template("meeting.md.j2")
    speakers = len({s.speaker for s in ri.segments if s.speaker != "?"})
    seg_rows = [
        {"speaker": s.speaker, "ts": _fmt_ts(s.start), "text": s.text}
        for s in ri.segments
    ]
    return tpl.render(
        date=ri.recorded_at.strftime("%Y-%m-%d"),
        time=ri.recorded_at.strftime("%H:%M"),
        duration=_fmt_ts(ri.duration_seconds),
        language=ri.language or "unknown",
        speakers=speakers,
        source_filename=ri.source_path.name,
        source_path=str(ri.source_path),
        user_name=ri.user_name,
        segments=seg_rows,
    )


def _slug(dt: datetime) -> str:
    return f"{dt.strftime('%Y-%m-%d %H%M%S')} — meeting"


class ObsidianWriter:
    def __init__(self, out_dir: Path, vault_name: str):
        self.out_dir = out_dir
        self.vault_name = vault_name
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def write(self, ri: RenderInput, markdown: str) -> tuple[Path, str]:
        fname = f"{_slug(ri.recorded_at)}.md"
        path = self.out_dir / fname
        path.write_text(markdown, encoding="utf-8")

        # obsidian:// URI — vault + file (file relative to vault root WITHOUT .md)
        vault_root = _find_vault_root(self.out_dir)
        if vault_root:
            rel = path.relative_to(vault_root).with_suffix("")
            uri = (
                f"obsidian://open?vault={urllib.parse.quote(self.vault_name)}"
                f"&file={urllib.parse.quote(str(rel))}"
            )
        else:
            uri = f"file://{urllib.parse.quote(str(path))}"
        return path, uri


class FolderWriter:
    def __init__(self, out_dir: Path):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def write(self, ri: RenderInput, markdown: str) -> tuple[Path, str]:
        fname = f"{_slug(ri.recorded_at)}.md"
        path = self.out_dir / fname
        path.write_text(markdown, encoding="utf-8")
        uri = f"file://{urllib.parse.quote(str(path))}"
        return path, uri


# ─── Obsidian vault discovery ──────────────────────────────────────────────

def _find_vault_root(path: Path) -> Path | None:
    """Walk up until we find a .obsidian/ sibling (vault root)."""
    for parent in [path, *path.parents]:
        if (parent / ".obsidian").is_dir():
            return parent
    return None


def discover_vaults() -> list[dict]:
    """Return list of {name, path} for all detectable Obsidian vaults."""
    home = Path.home()
    candidates: list[Path] = []

    icloud_root = home / "Library/Mobile Documents/iCloud~md~obsidian/Documents"
    if icloud_root.is_dir():
        candidates.extend(p for p in icloud_root.iterdir() if p.is_dir() and (p / ".obsidian").is_dir())

    nas_root = home / "NAS/Obsidian"
    if nas_root.is_dir():
        candidates.extend(p for p in nas_root.iterdir() if p.is_dir() and (p / ".obsidian").is_dir())

    for scan_root in (home / "Documents", home):
        if not scan_root.is_dir():
            continue
        try:
            for p in scan_root.iterdir():
                if p.is_dir() and (p / ".obsidian").is_dir() and p not in candidates:
                    candidates.append(p)
        except PermissionError:
            continue

    # Also read Obsidian's own vault list file (most authoritative)
    obsidian_cfg = home / "Library/Application Support/obsidian/obsidian.json"
    if obsidian_cfg.is_file():
        try:
            data = json.loads(obsidian_cfg.read_text())
            for v in (data.get("vaults") or {}).values():
                p = Path(v.get("path", ""))
                if p.is_dir() and (p / ".obsidian").is_dir() and p not in candidates:
                    candidates.append(p)
        except (json.JSONDecodeError, OSError):
            pass

    return [{"name": p.name, "path": str(p)} for p in candidates]
