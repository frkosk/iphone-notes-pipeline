"""Config loader. Minimal — only output location is user-tweakable.
Everything else (whisper model, language detect, diarize settings) is hard-coded
in constants.py because this is a hands-off pipeline, not a tuneable tool."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_CONFIG_PATH = Path.home() / "Library/Application Support/meet-transcriber/config.toml"


@dataclass
class OutputConfig:
    mode: str = "folder"            # "obsidian" | "folder"
    path: Path = field(default_factory=lambda: Path.home() / "Documents/MeetingTranscripts")
    vault_name: str = ""


@dataclass
class Config:
    source_path: Path
    output: OutputConfig
    db_path: Path
    log_path: Path


def _expand(p: str) -> Path:
    return Path(p).expanduser()


def load(path: Path | None = None) -> Config:
    cfg_path = path or DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"config not found: {cfg_path} — run `meet-transcriber reconfigure`")
    data = tomllib.loads(cfg_path.read_text())

    src = data.get("source", {})
    out = data.get("output", {})
    st = data.get("state", {})

    return Config(
        source_path=_expand(src.get("path", "~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings")),
        output=OutputConfig(
            mode=out.get("mode", "folder"),
            path=_expand(out.get("path", "~/Documents/MeetingTranscripts")),
            vault_name=out.get("vault_name", ""),
        ),
        db_path=_expand(st.get("db_path", "~/Library/Application Support/meet-transcriber/state.db")),
        log_path=_expand(st.get("log_path", "~/Library/Logs/meet-transcriber/daemon.log")),
    )


def write(cfg: Config, path: Path | None = None) -> Path:
    cfg_path = path or DEFAULT_CONFIG_PATH
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    content = f"""# meet-transcriber config (auto-generated)
# Only output location is tweakable here. Everything else is hard-coded —
# this is an automatic pipeline, not a dashboard. See src/meet_transcriber/constants.py.

[source]
path = "{cfg.source_path}"

[output]
mode = "{cfg.output.mode}"
path = "{cfg.output.path}"
vault_name = "{cfg.output.vault_name}"

[state]
db_path = "{cfg.db_path}"
log_path = "{cfg.log_path}"
"""
    cfg_path.write_text(content)
    return cfg_path
