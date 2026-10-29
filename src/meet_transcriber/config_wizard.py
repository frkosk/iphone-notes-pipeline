"""osascript-based config wizard. Shown by postinstall and `meet-transcriber reconfigure`."""
from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from .config import Config, OutputConfig, write
from .output import discover_vaults


def _osa(script: str) -> str:
    """Run AppleScript, return stdout (or raise on cancel)."""
    proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"user cancelled or osascript error: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _choose_mode() -> str:
    script = '''
    set theChoice to choose from list {"Obsidian vault", "Priečinok na disku"} \
        with title "meet-transcriber" \
        with prompt "Kam ukladať prepisy stretnutí?" \
        default items {"Obsidian vault"} \
        OK button name "Pokračovať" \
        cancel button name "Zrušiť"
    if theChoice is false then error "cancelled"
    return item 1 of theChoice
    '''
    choice = _osa(script)
    return "obsidian" if choice.startswith("Obsidian") else "folder"


def _choose_vault() -> tuple[str, Path]:
    """Returns (vault_name, vault_path)."""
    vaults = discover_vaults()
    if not vaults:
        return _manual_vault_pick()

    names_quoted = ", ".join(f'"{v["name"]}"' for v in vaults) + ', "[ Vybrať iný priečinok... ]"'
    script = f'''
    set theChoice to choose from list {{{names_quoted}}} \
        with title "Vyber Obsidian vault" \
        with prompt "Nájdené vaulty na tomto Macu:" \
        OK button name "Vybrať" \
        cancel button name "Zrušiť"
    if theChoice is false then error "cancelled"
    return item 1 of theChoice
    '''
    picked = _osa(script)
    if picked.startswith("["):
        return _manual_vault_pick()

    match = next(v for v in vaults if v["name"] == picked)
    return match["name"], Path(match["path"])


def _manual_vault_pick() -> tuple[str, Path]:
    script = '''
    set theFolder to choose folder with prompt "Vyber koreňový priečinok Obsidian vaultu (ten čo obsahuje .obsidian)"
    return POSIX path of theFolder
    '''
    path_str = _osa(script).rstrip("/")
    p = Path(path_str)
    return p.name, p


def _choose_subfolder(default: str = "Meetings") -> str:
    script = f'''
    set theName to text returned of (display dialog "Podpriečinok vo vaulte kam ukladať prepisy:" \
        default answer "{default}" \
        with title "meet-transcriber" \
        buttons {{"Zrušiť", "OK"}} default button "OK")
    return theName
    '''
    return _osa(script).strip() or default


def _choose_folder() -> Path:
    script = '''
    set defaultFolder to (path to home folder as string) & "Documents:MeetingTranscripts"
    try
        set theFolder to choose folder with prompt "Vyber priečinok pre .md prepisy:" default location (defaultFolder as alias)
    on error
        set theFolder to choose folder with prompt "Vyber priečinok pre .md prepisy:"
    end try
    return POSIX path of theFolder
    '''
    path_str = _osa(script).rstrip("/")
    return Path(path_str)


def _confirm(path: Path) -> bool:
    script = f'''
    display dialog "Prepisy sa budú ukladať do:\n\n{path}\n\nMôžeš to kedykoľvek zmeniť cez `meet-transcriber reconfigure`." \
        with title "meet-transcriber" \
        buttons {{"Zmeniť", "Hotovo"}} default button "Hotovo"
    return button returned of result
    '''
    try:
        answer = _osa(script)
        return answer == "Hotovo"
    except RuntimeError:
        return False


def run_wizard() -> Config:
    """Interactive wizard. Writes config.toml and returns Config."""
    while True:
        mode = _choose_mode()
        if mode == "obsidian":
            vault_name, vault_root = _choose_vault()
            subfolder = _choose_subfolder()
            out_path = vault_root / subfolder
            out_path.mkdir(parents=True, exist_ok=True)
            output = OutputConfig(mode="obsidian", path=out_path, vault_name=vault_name)
        else:
            folder = _choose_folder()
            folder.mkdir(parents=True, exist_ok=True)
            output = OutputConfig(mode="folder", path=folder, vault_name="")

        if _confirm(output.path):
            break

    cfg = Config(
        source_path=Path("~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings").expanduser(),
        output=output,
        db_path=Path("~/Library/Application Support/meet-transcriber/state.db").expanduser(),
        log_path=Path("~/Library/Logs/meet-transcriber/daemon.log").expanduser(),
    )
    write(cfg)
    return cfg
