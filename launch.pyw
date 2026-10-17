"""Nyanko-sensei launcher with per-user writable state."""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
os.environ["DSH_PET_SOURCE_LAUNCHER"] = str(ROOT / "launch.pyw")
for launcher_name in ("NyankoSensei.exe", "启动猫咪老师.exe"):
    launcher_exe = ROOT / launcher_name
    if sys.platform == "win32" and launcher_exe.is_file():
        os.environ["DSH_PET_SOURCE_EXECUTABLE"] = str(launcher_exe)
        break
sys.path.insert(0, str(ROOT))
from nyanko_paths import user_data_dir

USER_DATA = user_data_dir()
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
from pet import config as pet_config

# Preserve the configuration directory used by the validated Ubuntu packages.
if sys.platform.startswith("linux"):
    pet_config.APP_DIR_NAME = "dsh-pet-standalone-nyanko-sensei"
Config = pet_config.Config

initial_config = Config()
if not initial_config.path.exists():
    initial_config.set("character", "nyanko-sensei")
    initial_config.save()

sys.stdout = open(LOG_DIR / "launcher.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115 -- process-lifetime log
sys.stderr = sys.stdout
print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} launcher starting: {ROOT}", flush=True)

def run():
    sys.path.insert(0, str(ROOT))
    from pet import updater
    version_file = ROOT / 'version.txt'
    version = version_file.read_text(encoding='utf-8-sig').strip() if version_file.is_file() else '0.5.5'
    updater.configure_source('sfeng13/nyanko-sensei-pet', version)
    from nyanko_runtime import NyankoWindow
    from pet import app as pet_app
    pet_app.PetWindow = NyankoWindow
    args = list(sys.argv[1:])
    # Explicit slots (autostart) are preserved. Spawned children compete for
    # a free slot instead of being forced into the main pet's occupied slot.
    if '--slot' not in args and os.environ.get('DSH_PET_SPAWN_OFFSET_INDEX', '0') == '0':
        args += ['--slot', '0']
    return pet_app.main([str(ROOT / "launch.pyw"), *args], enable_chat=False)

if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except Exception:
        import traceback
        traceback.print_exc()
        raise
