"""Unicode Windows Shell links without PowerShell or WScript automation.

Uses IShellLinkW and IPersistFile, as documented by Microsoft:
https://learn.microsoft.com/windows/win32/shell/links
"""
from __future__ import annotations

import ctypes
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID


class _GUID(ctypes.Structure):
    _fields_ = [("data1", ctypes.c_uint32), ("data2", ctypes.c_uint16),
                ("data3", ctypes.c_uint16), ("data4", ctypes.c_ubyte * 8)]

    @classmethod
    def parse(cls, value):
        return cls.from_buffer_copy(UUID(value).bytes_le)


def _check(result):
    if result < 0:
        raise OSError(f"Windows Shell link failed: HRESULT 0x{result & 0xffffffff:08x}")


def _call(pointer, index, arguments, *values):
    table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    method = ctypes.WINFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, *arguments)(table[index])
    return method(pointer, *values)


@contextmanager
def _link():
    ole = ctypes.WinDLL("ole32")
    ole.CoUninitialize.argtypes = []
    ole.CoUninitialize.restype = None
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole.CoInitializeEx.restype = ctypes.c_int32
    # Qt may already own an apartment. Only uninitialize our successful call.
    initialized = ole.CoInitializeEx(None, 2)
    if initialized != -2147417850:  # RPC_E_CHANGED_MODE: existing apartment
        _check(initialized)
    shell = ctypes.c_void_p()
    persist = ctypes.c_void_p()
    try:
        clsid = _GUID.parse("00021401-0000-0000-c000-000000000046")
        iid = _GUID.parse("000214f9-0000-0000-c000-000000000046")
        ole.CoCreateInstance.argtypes = [ctypes.POINTER(_GUID), ctypes.c_void_p,
                                        ctypes.c_uint32, ctypes.POINTER(_GUID),
                                        ctypes.POINTER(ctypes.c_void_p)]
        ole.CoCreateInstance.restype = ctypes.c_int32
        _check(ole.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(shell)))
        iid_file = _GUID.parse("0000010b-0000-0000-c000-000000000046")
        _check(_call(shell, 0, [ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)],
                     ctypes.byref(iid_file), ctypes.byref(persist)))
        yield shell, persist
    finally:
        if persist:
            _call(persist, 2, [])
        if shell:
            _call(shell, 2, [])
        if initialized >= 0:
            ole.CoUninitialize()


def write_shortcut(path: Path, target: str, arguments: str, directory: str) -> None:
    with _link() as (shell, persist):
        for index, text in ((20, target), (11, arguments), (9, directory)):
            _check(_call(shell, index, [ctypes.c_wchar_p], text))
        _check(_call(shell, 15, [ctypes.c_int32], 7))  # SW_SHOWMINNOACTIVE
        _check(_call(persist, 6, [ctypes.c_wchar_p, ctypes.c_int32], str(path), 1))


def read_shortcut(path: Path) -> dict[str, str]:
    with _link() as (shell, persist):
        _check(_call(persist, 5, [ctypes.c_wchar_p, ctypes.c_uint32], str(path), 0))
        target = ctypes.create_unicode_buffer(32768)
        _check(_call(shell, 3, [ctypes.c_wchar_p, ctypes.c_int32, ctypes.c_void_p, ctypes.c_uint32],
                     target, len(target), None, 4))  # SLGP_RAWPATH
        result = {"target": target.value}
        for index, name in ((8, "directory"), (10, "arguments")):
            text = ctypes.create_unicode_buffer(32768)
            _check(_call(shell, index, [ctypes.c_wchar_p, ctypes.c_int32], text, len(text)))
            result[name] = text.value
        return result
