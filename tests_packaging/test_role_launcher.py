"""Exercise the shipped source entry without running its permanent event loop."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def launcher_result(tmp_path, args, *, child=False):
    env = os.environ.copy()
    env['XDG_CONFIG_HOME'] = str(tmp_path / 'config')
    env['XDG_STATE_HOME'] = str(tmp_path / 'state')
    env['LOCALAPPDATA'] = str(tmp_path / 'local')
    env['PYTHONPATH'] = str(ROOT / 'app') + os.pathsep + str(ROOT)
    env['DSH_PET_SPAWN_OFFSET_INDEX'] = '1' if child else '0'
    script = '''
import json, runpy, sys
from pet import app, updater
captured = {}
def main(argv, enable_chat=True):
    captured.update(argv=argv, enable_chat=enable_chat)
    return 0
app.main = main
sys.argv = ['launch.pyw', *json.loads(sys.argv[1])]
launcher = runpy.run_path('launch.pyw')
launcher['run']()
from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtGui import QDesktopServices
from pet.context_menus import registry
qt = QApplication([])
menu = QMenu()
QDesktopServices.openUrl = lambda url: captured.update(project_url=url.toString())
registry._build_github(menu, None).trigger()
captured.update(repo=updater.REPO, version=updater.APP_VERSION,
                newer=updater.is_newer('0.5.5'), mirrors=updater._UPDATE_JSON_URLS)
sys.__stdout__.write(json.dumps(captured))
'''
    result = subprocess.run([sys.executable, '-c', script, json.dumps(args)],
                            cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('args,child,expected', [
    ([], False, ['--slot', '0']),
    ([], True, []),
    (['--slot', '2'], True, ['--slot', '2']),
])
def test_role_launcher_preserves_slot_contract(tmp_path, args, child, expected):
    result = launcher_result(tmp_path, args, child=child)
    assert result['argv'][1:] == expected
    assert result['enable_chat'] is False


def test_role_launcher_checks_its_own_releases(tmp_path):
    result = launcher_result(tmp_path, [])
    assert result['repo'] == 'sfeng13/nyanko-sensei-pet'
    assert result['project_url'] == 'https://github.com/sfeng13/nyanko-sensei-pet'
    assert result['version'] == '0.5.4'
    assert result['newer'] is True
    # There is no Nyanko update.json; never fall back to upstream metadata.
    assert result['mirrors'] == []
