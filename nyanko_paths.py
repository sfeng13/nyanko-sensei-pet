"""Platform-specific writable paths, independent of the installation folder."""
import os
import sys
from pathlib import Path


def user_data_dir():
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "NyankoSensei"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "nyanko-sensei"
