import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nyanko_paths import user_data_dir  # noqa: E402


class PlatformPathsTests(unittest.TestCase):
    def test_linux_ignores_windows_environment(self):
        home = Path.home()
        with patch("nyanko_paths.sys.platform", "linux"), patch.dict(
            os.environ, {"LOCALAPPDATA": "windows-only", "USERPROFILE": str(home), "HOME": str(home)}, clear=True
        ):
            self.assertEqual(user_data_dir(), home / ".local/state/nyanko-sensei")

    def test_linux_respects_xdg_state(self):
        with patch("nyanko_paths.sys.platform", "linux"), patch.dict(
            os.environ, {"XDG_STATE_HOME": str(Path.home() / "custom-state")}
        ):
            self.assertEqual(user_data_dir(), Path.home() / "custom-state/nyanko-sensei")

    def test_windows_preserves_existing_path(self):
        with patch("nyanko_paths.sys.platform", "win32"), patch.dict(
            os.environ, {"LOCALAPPDATA": str(Path.home() / "local-test")}
        ):
            self.assertEqual(user_data_dir(), Path.home() / "local-test/NyankoSensei")
