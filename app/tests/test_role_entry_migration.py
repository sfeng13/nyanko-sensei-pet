from pathlib import Path

from pet import config, instance_launcher, updater


def test_child_process_uses_role_source_launcher(monkeypatch, tmp_path):
    launcher = tmp_path / '猫咪老师' / 'launch.pyw'
    launcher.parent.mkdir()
    launcher.write_text('# role entry', encoding='utf-8')
    monkeypatch.setenv('DSH_PET_SOURCE_LAUNCHER', str(launcher))
    monkeypatch.setattr(instance_launcher.sys, 'frozen', False, raising=False)
    assert instance_launcher.new_pet_command() == [instance_launcher.sys.executable, str(launcher)]


def test_linux_configuration_honors_xdg_directory(monkeypatch, tmp_path):
    monkeypatch.setattr(config.sys, 'platform', 'linux')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'settings'))
    assert config._default_base() == Path(tmp_path / 'settings')


def test_release_comparison_uses_configured_role_version(monkeypatch):
    monkeypatch.setattr(updater, 'APP_VERSION', '0.5.4')
    assert updater.is_newer('0.5.5')
    assert not updater.is_newer('0.5.4')
