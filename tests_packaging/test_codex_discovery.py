import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nyanko_codex_link as bridge  # noqa: E402


def test_windows_desktop_codex_found_without_path(tmp_path, monkeypatch):
    bins = tmp_path / "OpenAI" / "Codex" / "bin"
    (bins / "new-tools-only").mkdir(parents=True)
    old = bins / "old" / "codex.exe"
    old.parent.mkdir()
    old.write_bytes(b"test")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with patch.object(bridge.sys, "platform", "win32"), patch.object(bridge.shutil, "which", return_value=None):
        assert bridge.find_codex() == str(old)


def test_path_codex_has_priority(monkeypatch):
    with patch.object(bridge.shutil, "which", return_value="/usr/bin/codex"):
        assert bridge.find_codex() == "/usr/bin/codex"
