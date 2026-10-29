"""macOS notification via native osascript. No click action — user opens output manually."""
from __future__ import annotations

import subprocess


def _escape(s: str) -> str:
    """AppleScript string escape: double-quote and backslash."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def notify(title: str, message: str, open_url: str | None = None) -> None:
    """Show a macOS notification. open_url is accepted for API compat but ignored —
    osascript notifications have no click action. User opens the output in Obsidian
    or a file browser when ready."""
    script = (
        f'display notification "{_escape(message)}" '
        f'with title "{_escape(title)}" '
        f'sound name "Glass"'
    )
    subprocess.run(["osascript", "-e", script], capture_output=True)
