"""CLI: watch | process <file> | status | doctor | reconfigure"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


def _templates_dir() -> Path:
    """Templates live next to the installed package, or in repo/templates for dev."""
    env = os.environ.get("MEET_TRANSCRIBER_TEMPLATES")
    if env:
        return Path(env)
    # pkg layout: /usr/local/opt/meet-transcriber/templates
    pkg = Path("/usr/local/opt/meet-transcriber/templates")
    if pkg.is_dir():
        return pkg
    # dev: repo/templates (two levels up from this file: src/meet_transcriber/ → repo)
    return Path(__file__).resolve().parents[2] / "templates"


def _setup_logging(log_path: Path | None = None) -> None:
    # When running under launchd, stdout/stderr are already redirected to the log
    # file by the plist (StandardOutPath/StandardErrorPath). Writing to a
    # FileHandler as well would duplicate every line.
    # So we only emit to stderr; the plist does the file write.
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_path and sys.stderr.isatty():
        # Interactive run from a TTY — also mirror to the log file so you can
        # tail -f while debugging. Under launchd stderr is NOT a tty, so this
        # path is skipped.
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def cmd_process(args: argparse.Namespace) -> int:
    from .config import load
    from .pipeline import process_file

    cfg = load()
    _setup_logging(cfg.log_path)
    result = process_file(Path(args.file).expanduser(), cfg, _templates_dir(), force=args.force)
    if result:
        print(f"OK: {result}")
        return 0
    print("skipped (already processed, use --force)")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    from .config import load
    from .watcher import sweep

    cfg = load()
    _setup_logging(cfg.log_path)
    logging.info("sweep start")
    n = sweep(cfg, _templates_dir())
    logging.info(f"sweep done, processed {n} file(s)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from .config import load
    from .state import StateDB

    cfg = load()
    print(f"source:   {cfg.source_path}")
    print(f"output:   {cfg.output.mode} → {cfg.output.path}")
    if cfg.output.mode == "obsidian":
        print(f"vault:    {cfg.output.vault_name}")

    db = StateDB(cfg.db_path)
    try:
        ok = db.conn.execute("SELECT COUNT(*) FROM processed WHERE status='ok'").fetchone()[0]
        failed = db.conn.execute("SELECT COUNT(*) FROM processed WHERE status='failed'").fetchone()[0]
        print(f"processed: {ok} ok, {failed} failed")
    finally:
        db.close()
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    import shutil
    from .diarize import _find_cli as _find_who
    from .transcribe import _find_cli as _find_voz

    ok = True

    for tool in ("ffmpeg",):
        p = shutil.which(tool)
        print(f"  {tool}: {p or 'MISSING'}")
        if not p:
            ok = False

    for name, finder in (("voz-cli", _find_voz), ("who-cli", _find_who)):
        try:
            path = finder()
            print(f"  {name}: {path}")
        except FileNotFoundError as e:
            print(f"  {name}: MISSING ({e})")
            ok = False

    try:
        from .config import load
        cfg = load()
        print(f"  config:   OK ({cfg.output.mode} → {cfg.output.path})")
    except Exception as e:
        print(f"  config:   MISSING ({e})")
        ok = False

    print()
    print("OK" if ok else "ISSUES FOUND")
    return 0 if ok else 1


def cmd_reconfigure(args: argparse.Namespace) -> int:
    from .config_wizard import run_wizard
    cfg = run_wizard()
    print(f"saved: output.mode={cfg.output.mode} path={cfg.output.path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="meet-transcriber")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_watch = sub.add_parser("watch", help="scan source folder and process new files")
    p_watch.set_defaults(func=cmd_watch)

    p_process = sub.add_parser("process", help="process a single audio file")
    p_process.add_argument("file")
    p_process.add_argument("--force", action="store_true",
                           help="reprocess even if already in dedup DB")
    p_process.set_defaults(func=cmd_process)

    p_status = sub.add_parser("status", help="show config + dedup db summary")
    p_status.set_defaults(func=cmd_status)

    p_doctor = sub.add_parser("doctor", help="check dependencies")
    p_doctor.set_defaults(func=cmd_doctor)

    p_reconfig = sub.add_parser("reconfigure", help="run output picker wizard")
    p_reconfig.set_defaults(func=cmd_reconfigure)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
