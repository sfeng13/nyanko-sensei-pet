import json
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.codex_hooks import EVENTS, manage  # noqa: E402


def owned_count(config):
    total = 0
    for event in EVENTS:
        for group in config.get("hooks", {}).get(event, []):
            total += sum(
                1 for handler in group.get("hooks", [])
                if "nyanko_codex_hook.py" in handler.get("command", "")
            )
    return total


class CodexHookManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.codex = self.base / ".codex"
        self.codex.mkdir()
        self.install_root = self.base / "Programs" / "猫咪老师桌宠"
        self.hooks = self.codex / "hooks.json"

    def tearDown(self):
        self.temp.cleanup()

    def read(self):
        return json.loads(self.hooks.read_text(encoding="utf-8"))

    def test_install_repair_and_remove_preserve_other_hooks(self):
        existing = {
            "description": "keep me",
            "hooks": {
                "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "custom.exe"}]}],
                "Stop": [{"matcher": "*", "hooks": [{"type": "command", "command": "other-stop.exe"}]}],
            },
        }
        self.hooks.write_text(json.dumps(existing), encoding="utf-8")
        manage("install", self.install_root, self.hooks)
        first = self.read()
        self.assertEqual(first["description"], "keep me")
        self.assertEqual(owned_count(first), 3)
        self.assertEqual(first["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"], "custom.exe")
        self.assertEqual(len(list((self.codex / "backups").glob("hooks.json.*.bak"))), 1)

        manage("repair", self.install_root, self.hooks)
        self.assertEqual(owned_count(self.read()), 3)
        self.assertEqual(len(list((self.codex / "backups").glob("hooks.json.*.bak"))), 1)

        manage("remove", self.install_root, self.hooks)
        final = self.read()
        self.assertEqual(final["description"], "keep me")
        self.assertEqual(final["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"], "custom.exe")
        self.assertEqual(final["hooks"]["Stop"][0]["hooks"][0]["command"], "other-stop.exe")
        self.assertNotIn("Interrupt", final.get("hooks", {}))

    def test_commands_quote_unicode_and_spaced_paths(self):
        self.install_root = self.base / "Program Files" / "猫咪老师 桌宠"
        manage("install", self.install_root, self.hooks)
        config = self.read()
        commands = [
            handler["command"]
            for event in EVENTS
            for group in config["hooks"][event]
            for handler in group["hooks"]
        ]
        self.assertEqual(len(commands), 3)
        if sys.platform == "win32":
            self.assertTrue(all(command.startswith('"') for command in commands))
        else:
            self.assertTrue(all(shlex.split(command)[0] == str(Path(sys.executable).resolve()) for command in commands))
        self.assertTrue(all("猫咪老师 桌宠" in command for command in commands))

    def test_linux_commands_preserve_shell_special_paths(self):
        self.install_root = self.base / "猫咪老师 space '$ dollar"
        with patch("scripts.codex_hooks.sys.platform", "linux"):
            manage("install", self.install_root, self.hooks)
            for event, kind in zip(EVENTS, ("start", "stop", "interrupt")):
                command = self.read()["hooks"][event][0]["hooks"][0]["command"]
                self.assertEqual(shlex.split(command), [
                    str(Path(sys.executable).resolve()),
                    str((self.install_root / "nyanko_codex_hook.py").resolve()), kind,
                ])
            self.assertFalse(manage("repair", self.install_root, self.hooks)["changed"])

    def test_invalid_json_is_never_overwritten(self):
        original = b'{not json\n'
        self.hooks.write_bytes(original)
        with self.assertRaises(ValueError):
            manage("install", self.install_root, self.hooks)
        self.assertEqual(self.hooks.read_bytes(), original)
        self.assertFalse((self.codex / "backups").exists())

    def test_remove_does_not_create_a_file_when_uninstalled(self):
        result = manage("remove", self.install_root, self.hooks)
        self.assertFalse(result["changed"])
        self.assertFalse(self.hooks.exists())


if __name__ == "__main__":
    unittest.main()
