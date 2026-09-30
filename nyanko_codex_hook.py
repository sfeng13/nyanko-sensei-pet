"""Codex lifecycle hook: append minimal turn metadata for the local pet.

The prompt, answer, transcript and credentials are never written to the bridge.
Hook failures must never block a Codex turn.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def event_path() -> Path:
    override = os.environ.get("NYANKO_CODEX_EVENTS")
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "NyankoSenseiCodex" / "events.jsonl"
    return Path.home() / ".local" / "state" / "nyanko-sensei-codex" / "events.jsonl"


def write_event(kind: str, source: dict, path: Path | None = None) -> None:
    if kind not in {"start", "stop", "interrupt"}:
        return
    session_id = str(source.get("session_id") or "")[:128]
    turn_id = str(source.get("turn_id") or "")[:128]
    if not session_id or not turn_id:
        return
    record = {
        "event": kind,
        "session_id": session_id,
        "turn_id": turn_id,
        "ts": time.time(),
    }
    target = path or event_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(record, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)


def main() -> int:
    try:
        kind = sys.argv[1] if len(sys.argv) > 1 else ""
        source = json.load(sys.stdin)
        if isinstance(source, dict):
            write_event(kind, source)
    except Exception:
        pass  # A status indicator must not affect the conversation.
    print("{}")  # Stop/Interrupt hooks require JSON output.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
