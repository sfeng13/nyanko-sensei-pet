# -*- coding: utf-8 -*-
"""
开机自启动管理（跨平台）。

- Windows：角色启动器使用当前用户 Startup 快捷方式，普通版本使用 HKCU Run；
- macOS：LaunchAgents plist（~/Library/LaunchAgents/）；
- Linux：XDG autostart .desktop（~/.config/autostart/）。

设计原则：**系统自启配置是唯一真相**。菜单勾选状态直接查它们，不与 config.json
冗余存储，避免两处状态不同步。

命令按运行形态自适应：
- PyInstaller 打包（sys.frozen）：Windows 自启动先用 `start /D` 切到 exe 所在目录再启动 exe；
  macOS/Linux 指向 .app 内二进制自身 / onedir 内二进制自身；
- 源码运行：有角色启动器时保留它，否则使用 `python -m pet`（带工作目录）。
"""

from __future__ import annotations

import os
import json
import logging
import re
import shlex
import subprocess
import sys
from pathlib import Path

from .config import APP_DIR_NAME

# macOS LaunchAgent 按变体隔离（plist 文件名/Label），避免多版本互覆盖
_APP_BASE_ID = "com.merzlin.dsh-pet-standalone"
PLIST_LABEL = (
    _APP_BASE_ID
    if APP_DIR_NAME == "dsh-pet-standalone"
    else f"{_APP_BASE_ID}.{APP_DIR_NAME}"
)
# Windows 自启注册表值名按变体隔离（如 dsh-pet-standalone-webm-chat）。
# 每个变体只管理自己的值，避免“关无 Chat 版把 Chat 版也关了”。
VALUE_NAME = APP_DIR_NAME
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
# 历史/各变体可能写入过的值名；仅用于启动时清理“指向已不存在路径”的失效项，
# 不影响其他仍有效的变体自启。
KNOWN_VALUE_NAMES = (
    "dsh-pet-standalone",
    "dsh-pet-standalone-webm",
    "dsh-pet-standalone-webm-chat",
    "dsh-pet-standalone-gif",
    "dsh-pet-standalone-gif-chat",
)

_IS_WIN = sys.platform == "win32"
_IS_MAC = sys.platform == "darwin"
_IS_LINUX = sys.platform.startswith("linux")

if _IS_WIN:
    import winreg


def _project_root() -> Path:
    launcher = _source_launcher()
    if launcher is not None:
        return launcher.parent
    return Path(__file__).resolve().parent.parent


def _source_launcher() -> Path | None:
    raw = os.environ.get("DSH_PET_SOURCE_LAUNCHER")
    if raw:
        path = Path(raw)
        if path.is_absolute() and path.is_file():
            return path
    return None


def _plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"


def _desktop_path() -> Path:
    """Linux XDG autostart 目录（兼容无 XDG_CONFIG_HOME 的环境）。"""
    base = Path.home() / ".config"
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    if xdg:
        base = Path(xdg)
    return base / "autostart" / f"{PLIST_LABEL}.desktop"


def _linux_desktop_content() -> str:
    """Linux 自启 .desktop 内容；源码运行经 sh 切工作目录，打包运行直接指向二进制。"""
    if getattr(sys, "frozen", False):
        command = f"{shlex.quote(str(Path(sys.executable).resolve()))} --slot 0"
    else:
        root_quoted = shlex.quote(str(_project_root()))
        exe_quoted = shlex.quote(str(sys.executable))
        launcher = _source_launcher()
        entry = shlex.quote(str(launcher)) if launcher else "-m pet"
        inner_cmd = f"cd {root_quoted} && exec {exe_quoted} {entry} --slot 0"
        command = f"/bin/sh -c {shlex.quote(inner_cmd)}"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name=dsh-pet ({APP_DIR_NAME})\n"
        f"Exec={command}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
        "Comment=Desktop pet companion\n"
    )


def _pythonw_path() -> str:
    """Windows 源码运行时，取与 python.exe 同目录的 pythonw.exe（无控制台窗口）。"""
    exe = sys.executable
    if _IS_WIN and exe.lower().endswith("python.exe"):
        return exe[: -len("python.exe")] + "pythonw.exe"
    return exe


def _win_command_is_current(command: str) -> bool:
    """判断 Windows 自启命令是否已是“先切工作目录再启动”的新格式。"""
    return "cmd /c start" in command.lower()


def _iter_known_win_values() -> list[tuple[str, str]]:
    """读取注册表里所有已知 dsh-pet 自启值，返回 [(name, command), ...]。"""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            found = []
            for name in KNOWN_VALUE_NAMES:
                try:
                    command, _ = winreg.QueryValueEx(key, name)
                except FileNotFoundError:
                    continue
                found.append((name, str(command or "")))
            return found
    except OSError:
        return []


def _win_command_target_exists(command: str) -> bool:
    """判断 Windows 自启命令引用的路径是否仍然存在。

    命令格式形如：
      cmd /c start "" /D "C:\\path\\to\\dir" "C:\\path\\to\\app.exe"
    只要任一被引用的非空路径已不存在，就视为失效自启项。
    """
    if not isinstance(command, str) or not command.strip():
        return False
    quoted = re.findall(r'"([^"]*)"', command)
    paths = [item for item in quoted if item.strip()]
    if not paths:
        return True
    return all(Path(item).exists() for item in paths)


def cleanup_stale_entries() -> int:
    """清理指向已不存在路径的失效开机自启项（Windows）。

    用户“更新后直接删除旧目录但忘了关自启”时，HKCU Run 里会残留指向
    已删除路径的命令，导致每次开机弹终端报“找不到文件夹”。这里只删除
    路径已失效的已知 dsh-pet 项，不影响其他仍有效的变体自启。
    """
    if not _IS_WIN:
        return 0
    # Repair a moved/deleted role installation when the user next opens its
    # launcher. Do not revive a shortcut explicitly disabled by Windows.
    try:
        shortcut = _startup_shortcut_path()
        if _source_launcher() is not None and shortcut.is_file() and not _shortcut_disabled(shortcut):
            previous = _read_startup_shortcut(shortcut)
            if not Path(previous["target"]).is_file() or not Path(previous["directory"]).is_dir():
                if enable():
                    logging.info("已修复移动安装目录后失效的角色自启快捷方式")
    except (OSError, subprocess.SubprocessError):
        logging.warning("无法核对角色自启快捷方式", exc_info=True)
    removed = 0
    try:
        for name, command in _iter_known_win_values():
            if _win_command_target_exists(command):
                continue
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                try:
                    winreg.DeleteValue(key, name)
                    removed += 1
                except FileNotFoundError:
                    pass
    except OSError:
        pass
    return removed


def is_enabled() -> bool:
    """当前变体是否已注册开机自启；尊重 Windows 禁用状态。"""
    if _IS_WIN:
        try:
            shortcut = _startup_shortcut_path()
            if shortcut.exists():
                return not _shortcut_disabled(shortcut)
        except OSError:
            pass
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                command, _ = winreg.QueryValueEx(key, VALUE_NAME)
                # 兼容旧版：已开启但仍是旧命令（直接指向 exe，未切工作目录）时，
                # 自动升级为新命令，避免开机自启因 CWD 不可写而解压失败。
                if (
                    getattr(sys, "frozen", False)
                    and isinstance(command, str)
                    and not _win_command_is_current(command)
                ):
                    try:
                        with winreg.OpenKey(
                            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
                        ) as write_key:
                            winreg.SetValueEx(
                                write_key, VALUE_NAME, 0, winreg.REG_SZ, _win_command()
                            )
                    except OSError:
                        # 只读场景（如权限异常）不强求升级，仍视为已启用
                        pass
                return True
        except OSError:
            # 只认当前变体自己的值；其他变体的自启状态互不影响。
            return False
    if _IS_MAC:
        return _plist_path().exists()
    if _IS_LINUX:
        path = _desktop_path()
        # 兼容手动删除或 DE 禁用：文件存在即视为已开启（与 macOS 同策略）
        return path.exists()
    return False


def _win_command() -> str:
    if getattr(sys, "frozen", False):
        # onefile 的 runtime_tmpdir="." 是相对“当前工作目录”解析的；
        # 开机自启（HKCU Run）默认工作目录可能是 System32 等不可写目录。
        # 用 start 先切到 exe 所在目录再启动 exe，既保证解压目录在 exe 同目录，
        # 又不会让 cmd 窗口一直等待桌宠退出。开机自启固定指定 --slot 0。
        exe = Path(sys.executable).resolve()
        return f'cmd /c start "" /D "{exe.parent}" "{exe}" --slot 0'
    launcher = _source_launcher()
    executable = os.environ.get("DSH_PET_SOURCE_EXECUTABLE")
    if launcher and executable:
        path = Path(executable)
        if path.is_absolute() and path.is_file() and path.parent == launcher.parent:
            return f'"{path}" --slot 0'
    entry = f'"{launcher}"' if launcher else "-m pet"
    return f'cmd /c start "" /D "{_project_root()}" "{_pythonw_path()}" {entry} --slot 0'


def _mac_program_args() -> list[str]:
    if getattr(sys, "frozen", False):
        # .app 内二进制路径，直接作为 LaunchAgent 程序运行
        return [str(sys.executable), "--slot", "0"]
    launcher = _source_launcher()
    entry = [str(launcher)] if launcher else ["-m", "pet"]
    return [sys.executable, *entry, "--slot", "0"]


def _startup_shortcut_path() -> Path:
    """Use the real Windows Startup folder, not the launcher's overridden APPDATA."""
    import ctypes

    buffer = ctypes.create_unicode_buffer(32768)
    result = ctypes.windll.shell32.SHGetFolderPathW(None, 7, None, 0, buffer)
    if result != 0:
        raise OSError("Cannot locate current-user Startup folder")
    return Path(buffer.value) / f"{VALUE_NAME}.lnk"


def _shortcut_disabled(shortcut: Path) -> bool:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder",
        ) as key:
            value, _ = winreg.QueryValueEx(key, shortcut.name)
        return isinstance(value, bytes) and bool(value) and value[0] in (3, 7)
    except OSError:
        return False


def _startup_shell(script: str, environment: dict[str, str]) -> subprocess.CompletedProcess:
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    return subprocess.run(
        [str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
        env=environment, check=True, capture_output=True, timeout=15,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _read_startup_shortcut(shortcut: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["DSH_PET_STARTUP_READ"] = str(shortcut)
    result = _startup_shell(
        "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; "
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:DSH_PET_STARTUP_READ); "
        "@{target=$s.TargetPath;directory=$s.WorkingDirectory}|ConvertTo-Json -Compress",
        environment,
    )
    try:
        data = json.loads(result.stdout.decode("utf-8-sig"))
        if not isinstance(data, dict) or any(not isinstance(data.get(k), str) or not data[k] for k in ("target", "directory")):
            raise ValueError("Invalid shortcut metadata")
        return data
    except (ValueError, UnicodeError) as error:
        raise OSError("Cannot read startup shortcut") from error


def _remove_owned_run() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        # New user profiles need not have an HKCU Run key at all.
        pass


def _write_startup_shortcut() -> None:
    launcher = _source_launcher()
    if launcher is None:
        raise OSError("Missing role launcher")
    executable = Path(os.environ.get("DSH_PET_SOURCE_EXECUTABLE", ""))
    if executable.is_absolute() and executable.is_file() and executable.parent == launcher.parent:
        target, arguments = str(executable), "--slot 0"
    else:
        target, arguments = _pythonw_path(), f'"{launcher}" --slot 0'
    if not Path(target).is_file():
        raise OSError("Startup executable is missing")
    shortcut = _startup_shortcut_path()
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["DSH_PET_STARTUP_LINK"] = json.dumps({
        "path": str(shortcut), "target": target, "arguments": arguments,
        "directory": str(launcher.parent),
    }, ensure_ascii=False)
    # Pass paths as data, never interpolate them into executable shell code.
    _startup_shell(
        "$ErrorActionPreference='Stop'; $d=$env:DSH_PET_STARTUP_LINK|ConvertFrom-Json; "
        "$w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut($d.path); "
        "$s.TargetPath=$d.target; $s.Arguments=$d.arguments; "
        "$s.WorkingDirectory=$d.directory; $s.WindowStyle=7; $s.Save(); "
        "$v=$w.CreateShortcut($d.path); "
        "if($v.TargetPath -ne $d.target -or $v.Arguments -ne $d.arguments -or "
        "$v.WorkingDirectory -ne $d.directory){throw 'Startup shortcut readback failed'}",
        environment,
    )
    if not shortcut.is_file():
        raise OSError("Startup shortcut was not saved")
    # Explicitly enabling in our menu restores our own OS-disabled entry only.
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder",
            0, winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, shortcut.name)
    except FileNotFoundError:
        pass


def enable() -> bool:
    """开启自启；返回是否写入成功（Windows 回读注册表验证，macOS 验证 plist 存在，Linux 验证 .desktop 存在）。"""
    if _IS_WIN:
        try:
            if _source_launcher() is not None:
                _write_startup_shortcut()
                # Remove the previous route only after its replacement is saved.
                _remove_owned_run()
                return is_enabled()
            # 只写当前变体自己的值，不影响其他 Chat/无 Chat 变体的自启状态。
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _win_command())
            # 回读验证，防止写入被安全软件/策略静默拦截
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
        except (OSError, subprocess.SubprocessError):
            logging.warning("Windows 开机自启设置失败", exc_info=True)
            return False
    elif _IS_MAC:
        import plistlib

        try:
            _plist_path().parent.mkdir(parents=True, exist_ok=True)
            plist: dict = {
                "Label": PLIST_LABEL,
                "ProgramArguments": _mac_program_args(),
                "RunAtLoad": True,
            }
            if not getattr(sys, "frozen", False):
                plist["WorkingDirectory"] = str(_project_root())
            with _plist_path().open("wb") as f:
                plistlib.dump(plist, f)
            return _plist_path().exists()
        except OSError:
            return False
    elif _IS_LINUX:
        try:
            path = _desktop_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_linux_desktop_content(), encoding="utf-8")
            return path.exists()
        except OSError:
            return False
    return False


def disable() -> bool:
    """关闭自启；返回是否已清除。"""
    if _IS_WIN:
        try:
            _startup_shortcut_path().unlink(missing_ok=True)
            _remove_owned_run()
            return True
        except OSError:
            return False
    elif _IS_MAC:
        try:
            _plist_path().unlink(missing_ok=True)
            return True
        except OSError:
            return False
    elif _IS_LINUX:
        try:
            _desktop_path().unlink(missing_ok=True)
            return True
        except OSError:
            return False
    return True


def set_enabled(on: bool) -> bool:
    return enable() if on else disable()
