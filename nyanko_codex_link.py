"""Read-only Codex turn bridge and official App Server quota reader."""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path


def event_path() -> Path:
    override = os.environ.get("NYANKO_CODEX_EVENTS")
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "NyankoSenseiCodex" / "events.jsonl"
    return Path.home() / ".local" / "state" / "nyanko-sensei-codex" / "events.jsonl"


class EventFeed:
    def __init__(self, path: Path | None = None):
        self.path = path or event_path()
        self.offset = self.path.stat().st_size if self.path.is_file() else 0
        self.tail = b""

    def read(self) -> list[dict]:
        try:
            size = self.path.stat().st_size
            if size < self.offset:
                self.offset, self.tail = 0, b""
            with self.path.open("rb") as stream:
                stream.seek(self.offset)
                chunk = stream.read(65536)
                self.offset = stream.tell()
        except OSError:
            return []
        if not chunk:
            return []
        pieces = (self.tail + chunk).split(b"\n")
        self.tail = pieces.pop()[-4096:]
        events = []
        for raw in pieces:
            try:
                item = json.loads(raw)
                if (item.get("event") in {"start", "stop", "interrupt"}
                        and isinstance(item.get("session_id"), str)
                        and isinstance(item.get("turn_id"), str)):
                    events.append(item)
            except (ValueError, TypeError, AttributeError):
                continue
        return events


class TurnState:
    def __init__(self):
        self.active: set[tuple[str, str]] = set()

    def apply(self, event: dict) -> str | None:
        key = (event["session_id"], event["turn_id"])
        kind = event["event"]
        if kind == "start":
            if key in self.active:
                return None
            self.active.add(key)
            return "start" if len(self.active) == 1 else "concurrent"
        if key not in self.active:
            return None
        self.active.remove(key)
        if self.active:
            return "still_active"
        return kind


def _receive_id(out: queue.Queue, wanted: int, timeout: float) -> dict:
    import time
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Codex App Server did not respond")
        message = out.get(timeout=remaining)
        if message.get("id") == wanted:
            return message


def read_quota(timeout: float = 8.0) -> dict:
    """Read subscription limits; never starts a model turn or copies auth tokens."""
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("找不到 Codex CLI")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen(
        [codex, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1,
        creationflags=flags,
    )
    messages: queue.Queue[dict] = queue.Queue()

    def reader() -> None:
        for line in proc.stdout:
            try:
                messages.put(json.loads(line))
            except ValueError:
                continue

    threading.Thread(target=reader, daemon=True).start()

    def send(record: dict) -> None:
        proc.stdin.write(json.dumps(record) + "\n")
        proc.stdin.flush()

    try:
        send({"method": "initialize", "id": 1, "params": {"clientInfo": {
            "name": "nyanko_sensei_pet", "title": "Nyanko-sensei Pet", "version": "0.5.3"}}})
        if "error" in _receive_id(messages, 1, timeout):
            raise RuntimeError("Codex 初始化失败")
        send({"method": "initialized", "params": {}})
        send({"method": "account/rateLimits/read", "id": 2})
        answer = _receive_id(messages, 2, timeout)
        if "error" in answer:
            raise RuntimeError("Codex 额度查询失败")
        result = answer.get("result") or {}
        return (result.get("rateLimitsByLimitId") or {}).get("codex") or result.get("rateLimits") or {}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def quota_text(limits: dict) -> str:
    parts = []
    for label, key in (("5 小时", "primary"), ("本周", "secondary")):
        window = limits.get(key)
        if not isinstance(window, dict) or window.get("usedPercent") is None:
            continue
        used = max(0.0, min(100.0, float(window["usedPercent"])))
        remaining = round(100.0 - used)
        parts.append(f"{label}剩余 {remaining}%")
    return " · ".join(parts) if parts else "额度暂时查不到"
