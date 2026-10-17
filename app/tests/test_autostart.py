# -*- coding: utf-8 -*-
"""开机自启模块测试（Linux XDG autostart 分支 + Windows 变体隔离）。"""

from pathlib import Path
import sys

import pytest

from pet import autostart as autostart_mod


class FakeWinreg:
    """极简 winreg 替身：用 dict 模拟 HKCU Run 值，验证变体互不影响。"""

    HKEY_CURRENT_USER = object()
    KEY_SET_VALUE = 1
    REG_SZ = 1

    def __init__(self):
        self.values = {}

    def OpenKey(self, root, subkey, reserved=0, access=0):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def QueryValueEx(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        return self.values[name], 1

    def SetValueEx(self, key, name, reserved, value_type, value):
        self.values[name] = value

    def DeleteValue(self, key, name):
        if name not in self.values:
            raise FileNotFoundError(name)
        del self.values[name]


def _force_win(monkeypatch):
    monkeypatch.setattr(autostart_mod, "_IS_WIN", True)
    monkeypatch.setattr(autostart_mod, "_IS_MAC", False)
    monkeypatch.setattr(autostart_mod, "_IS_LINUX", False)
    fake = FakeWinreg()
    # Linux/macOS 模块不会自动 import winreg，用 raising=False 补挂测试替身。
    monkeypatch.setattr(autostart_mod, "winreg", fake, raising=False)
    monkeypatch.setattr(autostart_mod, "_startup_shortcut_path", lambda: Path("unused-test-startup.lnk"))
    return fake


def test_windows_source_launcher_is_preserved(monkeypatch, tmp_path):
    _force_win(monkeypatch)
    launcher = tmp_path / "猫咪老师 folder" / "launch.pyw"
    launcher.parent.mkdir()
    launcher.write_text("", encoding="utf-8")
    monkeypatch.setenv("DSH_PET_SOURCE_LAUNCHER", str(launcher))
    monkeypatch.setattr(autostart_mod.sys, "frozen", False, raising=False)
    command = autostart_mod._win_command()
    assert f'"{launcher}"' in command
    assert f'/D "{launcher.parent}"' in command
    assert "-m pet" not in command


def test_windows_role_executable_autostart_needs_no_cmd(monkeypatch, tmp_path):
    _force_win(monkeypatch)
    launcher = tmp_path / "猫咪老师 folder" / "launch.pyw"
    launcher.parent.mkdir()
    launcher.write_text("", encoding="utf-8")
    executable = launcher.parent / "NyankoSensei.exe"
    executable.write_bytes(b"test")
    monkeypatch.setenv("DSH_PET_SOURCE_LAUNCHER", str(launcher))
    monkeypatch.setenv("DSH_PET_SOURCE_EXECUTABLE", str(executable))
    monkeypatch.setattr(autostart_mod.sys, "frozen", False, raising=False)
    assert autostart_mod._win_command() == f'"{executable}" --slot 0'


def test_windows_role_startup_shortcut_replaces_only_owned_run(monkeypatch, tmp_path):
    fake = _force_win(monkeypatch)
    launcher = tmp_path / "猫咪老师 folder" / "launch.pyw"
    launcher.parent.mkdir()
    launcher.write_text("", encoding="utf-8")
    monkeypatch.setenv("DSH_PET_SOURCE_LAUNCHER", str(launcher))
    shortcut = tmp_path / "Startup" / "pet.lnk"
    monkeypatch.setattr(autostart_mod, "_startup_shortcut_path", lambda: shortcut)
    monkeypatch.setattr(autostart_mod, "_write_startup_shortcut", lambda: (
        shortcut.parent.mkdir(exist_ok=True), shortcut.write_bytes(b"shortcut")
    ))
    fake.values[autostart_mod.VALUE_NAME] = "old command"
    fake.values["other-app"] = "keep"
    assert autostart_mod.enable()
    assert shortcut.exists()
    assert autostart_mod.VALUE_NAME not in fake.values
    assert fake.values["other-app"] == "keep"
    assert autostart_mod.is_enabled()
    assert autostart_mod.disable()
    assert not shortcut.exists()
    assert fake.values["other-app"] == "keep"


def test_windows_shortcut_failure_preserves_old_startup(monkeypatch, tmp_path):
    fake = _force_win(monkeypatch)
    launcher = tmp_path / "launch.pyw"
    launcher.write_text("", encoding="utf-8")
    monkeypatch.setenv("DSH_PET_SOURCE_LAUNCHER", str(launcher))
    monkeypatch.setattr(autostart_mod, "_startup_shortcut_path", lambda: tmp_path / "pet.lnk")
    def fail():
        raise OSError("shortcut denied")
    monkeypatch.setattr(autostart_mod, "_write_startup_shortcut", fail)
    fake.values[autostart_mod.VALUE_NAME] = "old command"
    assert not autostart_mod.enable()
    assert fake.values[autostart_mod.VALUE_NAME] == "old command"


def test_windows_shortcut_disabled_in_system_is_not_checked(monkeypatch, tmp_path):
    fake = _force_win(monkeypatch)
    shortcut = tmp_path / "pet.lnk"
    shortcut.write_bytes(b"shortcut")
    monkeypatch.setattr(autostart_mod, "_startup_shortcut_path", lambda: shortcut)
    fake.values[shortcut.name] = bytes([3]) + bytes(11)
    assert not autostart_mod.is_enabled()
    fake.values[shortcut.name] = bytes([2]) + bytes(11)
    assert autostart_mod.is_enabled()


def test_windows_fresh_profile_without_run_key_can_enable_and_disable(monkeypatch, tmp_path):
    fake = _force_win(monkeypatch)
    launcher = tmp_path / "launch.pyw"
    launcher.write_text("", encoding="utf-8")
    monkeypatch.setenv("DSH_PET_SOURCE_LAUNCHER", str(launcher))
    shortcut = tmp_path / "pet.lnk"
    monkeypatch.setattr(autostart_mod, "_startup_shortcut_path", lambda: shortcut)
    monkeypatch.setattr(autostart_mod, "_write_startup_shortcut", lambda: shortcut.write_bytes(b"link"))
    open_key = fake.OpenKey

    def missing_run(root, subkey, reserved=0, access=0):
        if subkey == autostart_mod.RUN_KEY:
            raise FileNotFoundError("fresh profile")
        return open_key(root, subkey, reserved, access)

    monkeypatch.setattr(fake, "OpenKey", missing_run)
    assert autostart_mod.enable()
    assert autostart_mod.is_enabled()
    assert autostart_mod.disable()
    assert not autostart_mod.is_enabled()


def test_windows_moved_role_repairs_enabled_shortcut(monkeypatch, tmp_path):
    _force_win(monkeypatch)
    launcher = tmp_path / "new install" / "launch.pyw"
    launcher.parent.mkdir()
    launcher.write_text("", encoding="utf-8")
    monkeypatch.setenv("DSH_PET_SOURCE_LAUNCHER", str(launcher))
    shortcut = tmp_path / "pet.lnk"
    shortcut.write_bytes(b"old link")
    monkeypatch.setattr(autostart_mod, "_startup_shortcut_path", lambda: shortcut)
    monkeypatch.setattr(autostart_mod, "_read_startup_shortcut", lambda path: {
        "target": str(tmp_path / "deleted install" / "pet.exe"),
        "directory": str(tmp_path / "deleted install"),
    }, raising=False)
    monkeypatch.setattr(autostart_mod, "_write_startup_shortcut", lambda: shortcut.write_bytes(b"repaired"))
    autostart_mod.cleanup_stale_entries()
    assert shortcut.read_bytes() == b"repaired"


def test_windows_moved_role_respects_system_disabled_shortcut(monkeypatch, tmp_path):
    fake = _force_win(monkeypatch)
    launcher = tmp_path / "launch.pyw"
    launcher.write_text("", encoding="utf-8")
    monkeypatch.setenv("DSH_PET_SOURCE_LAUNCHER", str(launcher))
    shortcut = tmp_path / "pet.lnk"
    shortcut.write_bytes(b"disabled")
    monkeypatch.setattr(autostart_mod, "_startup_shortcut_path", lambda: shortcut)
    fake.values[shortcut.name] = bytes([3]) + bytes(11)
    autostart_mod.cleanup_stale_entries()
    assert shortcut.read_bytes() == b"disabled"


@pytest.mark.skipif(sys.platform != "win32", reason="real Windows Shell shortcut")
def test_windows_actual_shortcut_moves_between_unicode_install_paths(monkeypatch, tmp_path):
    _force_win(monkeypatch)
    shortcut = tmp_path / "Startup" / "review.lnk"
    monkeypatch.setattr(autostart_mod, "_startup_shortcut_path", lambda: shortcut)
    executables = []
    for folder in ("旧目录 中文 [$] 'space", "新环境 中文 [$] 'space"):
        root = tmp_path / folder
        root.mkdir()
        launcher = root / "launch.pyw"
        launcher.write_text("", encoding="utf-8")
        executable = root / "NyankoSensei.exe"
        # Shell versions may reject a two-byte MZ placeholder as an invalid
        # executable. Test real links with a real PE file, without running it.
        executable.write_bytes(Path(sys.executable).read_bytes())
        executables.append(executable)
        monkeypatch.setenv("DSH_PET_SOURCE_LAUNCHER", str(launcher))
        monkeypatch.setenv("DSH_PET_SOURCE_EXECUTABLE", str(executable))
        if len(executables) == 1:
            assert autostart_mod.enable()
        else:
            executables[0].unlink()
            autostart_mod.cleanup_stale_entries()
        data = autostart_mod._read_startup_shortcut(shortcut)
        assert Path(data["target"]) == executable
        assert Path(data["directory"]) == root
    assert autostart_mod.disable()
    assert not shortcut.exists()


def test_windows_autostart_variants_do_not_affect_each_other(monkeypatch):
    fake = _force_win(monkeypatch)
    monkeypatch.setattr(autostart_mod, "VALUE_NAME", "dsh-pet-standalone-webm")

    assert autostart_mod.enable() is True
    assert "dsh-pet-standalone-webm" in fake.values
    assert autostart_mod.is_enabled() is True

    # 切到 Chat 变体再开启：不应清掉无 Chat 版的自启
    monkeypatch.setattr(autostart_mod, "VALUE_NAME", "dsh-pet-standalone-webm-chat")
    assert autostart_mod.enable() is True
    assert "dsh-pet-standalone-webm" in fake.values
    assert "dsh-pet-standalone-webm-chat" in fake.values

    # 关闭 Chat 版：无 Chat 版必须保留
    assert autostart_mod.disable() is True
    assert "dsh-pet-standalone-webm-chat" not in fake.values
    assert "dsh-pet-standalone-webm" in fake.values

    # is_enabled 只认当前变体自己的值
    assert autostart_mod.is_enabled() is False
    monkeypatch.setattr(autostart_mod, "VALUE_NAME", "dsh-pet-standalone-webm")
    assert autostart_mod.is_enabled() is True


def test_cleanup_stale_entries_removes_only_missing_paths(monkeypatch, tmp_path):
    fake = _force_win(monkeypatch)
    existing_dir = tmp_path / "existing"
    existing_dir.mkdir()
    existing_exe = existing_dir / "dsh-pet.exe"
    existing_exe.write_bytes(b"MZ")
    missing_dir = tmp_path / "deleted"
    missing_exe = missing_dir / "dsh-pet.exe"

    fake.values = {
        "dsh-pet-standalone-webm": (
            f'cmd /c start "" /D "{existing_dir}" "{existing_exe}"'
        ),
        "dsh-pet-standalone-webm-chat": (
            f'cmd /c start "" /D "{missing_dir}" "{missing_exe}"'
        ),
    }

    removed = autostart_mod.cleanup_stale_entries()

    assert removed == 1
    assert "dsh-pet-standalone-webm" in fake.values
    assert "dsh-pet-standalone-webm-chat" not in fake.values


def _force_linux(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(autostart_mod, "_IS_WIN", False)
    monkeypatch.setattr(autostart_mod, "_IS_MAC", False)
    monkeypatch.setattr(autostart_mod, "_IS_LINUX", True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


def test_linux_enable_writes_desktop_file(monkeypatch, tmp_path: Path):
    _force_linux(monkeypatch, tmp_path)
    desktop = tmp_path / "autostart" / f"{autostart_mod.PLIST_LABEL}.desktop"
    assert not desktop.exists()
    assert autostart_mod.is_enabled() is False

    assert autostart_mod.enable() is True
    assert desktop.exists()
    assert autostart_mod.is_enabled() is True
    content = desktop.read_text(encoding="utf-8")
    assert "[Desktop Entry]" in content
    assert "Type=Application" in content
    assert content.startswith("Exec=") or "\nExec=" in content
    assert "Terminal=false" in content


def test_linux_disable_removes_desktop_file(monkeypatch, tmp_path: Path):
    _force_linux(monkeypatch, tmp_path)
    assert autostart_mod.enable() is True
    assert autostart_mod.disable() is True
    assert autostart_mod.is_enabled() is False
    desktop = tmp_path / "autostart" / f"{autostart_mod.PLIST_LABEL}.desktop"
    assert not desktop.exists()
