"""SQLite dedup index for processed audio files."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def fingerprint(audio_path: Path) -> str:
    """sha256 of (size + first 1 MB) — fast + reliable for Voice Memos."""
    size = audio_path.stat().st_size
    h = hashlib.sha256()
    h.update(str(size).encode())
    with open(audio_path, "rb") as f:
        h.update(f.read(1024 * 1024))
    return h.hexdigest()


class StateDB:
    def __init__(self, db_path: Path):
        _ensure_dir(db_path)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS processed (
                fp TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                size INTEGER NOT NULL,
                output_path TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ok',
                error TEXT,
                processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migration: add missing columns on existing DBs
        try:
            self.conn.execute("ALTER TABLE processed ADD COLUMN status TEXT NOT NULL DEFAULT 'ok'")
        except sqlite3.OperationalError:
            pass
        try:
            self.conn.execute("ALTER TABLE processed ADD COLUMN error TEXT")
        except sqlite3.OperationalError:
            pass
        self.conn.commit()

    def is_processed(self, fp: str) -> bool:
        """True if seen before — regardless of ok/failed status.
        Failed files are skipped so they don't infinite-loop; use `--force` to retry."""
        row = self.conn.execute("SELECT 1 FROM processed WHERE fp = ?", (fp,)).fetchone()
        return row is not None

    def mark_processed(self, fp: str, filename: str, size: int, output_path: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO processed (fp, filename, size, output_path, status, error) "
            "VALUES (?, ?, ?, ?, 'ok', NULL)",
            (fp, filename, size, output_path),
        )
        self.conn.commit()

    def mark_failed(self, fp: str, filename: str, size: int, error: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO processed (fp, filename, size, output_path, status, error) "
            "VALUES (?, ?, ?, '', 'failed', ?)",
            (fp, filename, size, error[:500]),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
