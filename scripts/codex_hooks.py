"""Safely install, repair, inspect, or remove Nyanko-sensei Codex hooks.

Only lifecycle metadata is handled by the hook script. This manager never
reads transcripts, tokens, or credentials, and it preserves unrelated hooks.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EVENTS = ("UserPromptSubmit", "Stop", "Interrupt")
HOOK_SCRIPT = "nyanko_codex_hook.py"


def codex_home() -> Path:
    override = os.environ.get("CODEX_HOME")
    if override:
        return Path(override).expanduser()
    profile = os.environ.get("USERPROFILE")
    return (Path(profile) if profile else Path.home()) / ".codex"


def hooks_path() -> Path:
    return codex_home() / "hooks.json"


def _command(host: Path, hook_script: Path, event: str) -> str:
    # Windows Codex executes this as a command line. Quote each path so Unicode,
    # spaces, and punctuation in the per-user install folder remain intact.
    return f'"{host.resolve()}" "{hook_script.resolve()}" {event}'


def _is_ours(handler: Any) -> bool:
    return (
        isinstance(handler, dict)
        and handler.get("type") == "command"
        and HOOK_SCRIPT.casefold() in str(handler.get("command", "")).casefold()
    )


def _load(path: Path) -> tuple[dict[str, Any], bytes | None]:
    if not path.exists():
        return {}, None
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法解析现有 hooks.json，已保留原文件：{path}") from exc
    if not isinstance(value, dict):
        raise ValueError("现有 hooks.json 顶层必须是 JSON 对象；原文件未修改。")
    return value, raw


def _without_ours(hooks: dict[str, Any]) -> bool:
    changed = False
    for event, groups in list(hooks.items()):
        if not isinstance(groups, list):
            continue
        new_groups = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                new_groups.append(group)
                continue
            handlers = group["hooks"]
            kept = [handler for handler in handlers if not _is_ours(handler)]
            if len(kept) != len(handlers):
                changed = True
            if kept:
                if len(kept) != len(handlers):
                    next_group = dict(group)
                    next_group["hooks"] = kept
                    new_groups.append(next_group)
                else:
                    new_groups.append(group)
            elif len(kept) != len(handlers):
                remainder = {key: value for key, value in group.items() if key != "hooks"}
                if remainder:
                    new_groups.append(remainder)
            else:
                new_groups.append(group)
        if new_groups:
            hooks[event] = new_groups
        elif groups:
            hooks.pop(event, None)
            changed = True
    return changed


def _backup(path: Path, original: bytes | None) -> Path | None:
    if original is None:
        return None
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"hooks.json.{stamp}.bak"
    suffix = 1
    while backup.exists():
        backup = backup_dir / f"hooks.json.{stamp}.{suffix}.bak"
        suffix += 1
    backup.write_bytes(original)
    return backup


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    fd, temp_name = tempfile.mkstemp(prefix="hooks.json.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def manage(action: str, root: Path, path: Path | None = None) -> dict[str, Any]:
    target = path or hooks_path()
    config, original = _load(target)
    initial_config = copy.deepcopy(config)
    hooks = config.get("hooks", {})
    if hooks is None:
        hooks = {}
    if not isinstance(hooks, dict):
        raise ValueError("hooks.json 的 hooks 字段必须是对象；原文件未修改。")
    hooks = copy.deepcopy(hooks)

    if action == "status":
        found = {event: 0 for event in EVENTS}
        for event, groups in hooks.items():
            if event in found and isinstance(groups, list):
                found[event] = sum(
                    1 for group in groups
                    if isinstance(group, dict)
                    for handler in group.get("hooks", [])
                    if _is_ours(handler)
                )
        return {"path": str(target), "installed": any(found.values()), "events": found}

    changed = _without_ours(hooks)
    if action in {"install", "repair"}:
        host = root / "HookHost.exe"
        script = root / HOOK_SCRIPT
        for event, kind in zip(EVENTS, ("start", "stop", "interrupt")):
            groups = hooks.setdefault(event, [])
            if not isinstance(groups, list):
                raise ValueError(f"hooks.{event} 必须是数组；原文件未修改。")
            groups.append({"hooks": [{
                "type": "command",
                "command": _command(host, script, kind),
                "timeout": 3,
                "statusMessage": "猫咪老师桌宠同步 Codex 状态",
            }]})
        changed = True

    if action in {"install", "repair", "remove"}:
        if hooks:
            config["hooks"] = hooks
        else:
            config.pop("hooks", None)
        changed = config != initial_config
    if changed:
        _backup(target, original)
        _atomic_json(target, config)
    return {"path": str(target), "changed": changed, "action": action}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "repair", "remove", "status"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--hooks-file", type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(manage(args.action, args.root, args.hooks_file), ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
