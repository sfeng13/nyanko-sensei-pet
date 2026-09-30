"""Nyanko-sensei launcher with per-user writable state."""
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
USER_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "NyankoSensei"
APP_DATA = USER_DATA / "data"
LOG_DIR = USER_DATA / "logs"
APP_DATA.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
# The application treats APPDATA as its configuration root. Keep it outside the
# Program Files-style install directory so updates never replace personal state.
os.environ["APPDATA"] = str(APP_DATA)
sys.path.insert(0, str(ROOT / "app"))
# A clean installation should start with the bundled Nyanko character. Existing
# user selection and settings are preserved on every subsequent launch.
from pet.config import Config

initial_config = Config()
if not initial_config.path.exists():
    initial_config.set("character", "nyanko-sensei")
    initial_config.save()

sys.stdout = open(LOG_DIR / "launcher.log", "a", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout

def run():
    sys.path.insert(0, str(ROOT))
    from pet import app as pet_app
    from nyanko_runtime import NyankoWindow
    pet_app.PetWindow = NyankoWindow
    return pet_app.main([str(ROOT / "launch.pyw"), "--slot", "0"], enable_chat=False)

if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        import traceback
        traceback.print_exc()
        raise
