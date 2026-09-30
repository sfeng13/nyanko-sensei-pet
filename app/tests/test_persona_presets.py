# -*- coding: utf-8 -*-
"""内置台词预设（data-over-code）加载与数据契约测试。

预设文案不写死在 pet/persona_phrases.py 代码里，而是外置为
pet/persona_presets/{legacy,whale_maid}.json：模块导入（启动）时加载一次，
「重设/恢复内置」经 reload_builtin_presets() 重新读盘。这里锁定数据契约：
预设文件存在且为合法 JSON、事件键与导出 schema（persona_template）对齐、
占位符不越过 PARAMETERS 渲染契约、拾取器按 mode 输出预设文案。
"""
import json
import re
from pathlib import Path

from pet.persona_phrases import (
    PhrasePicker,
    builtin_phrases,
    load_builtin_presets,
    phrase_keys,
    reload_builtin_presets,
)

PRESET_DIR = Path(__file__).resolve().parents[1] / "pet" / "persona_presets"
BUILTIN_MODES = ("legacy", "whale_maid")


def _read_preset_file(mode: str) -> dict:
    return json.loads((PRESET_DIR / f"{mode}.json").read_text(encoding="utf-8"))


def test_builtin_preset_files_exist_and_are_nonempty_event_maps():
    for mode in BUILTIN_MODES:
        raw = _read_preset_file(mode)
        assert isinstance(raw, dict)
        assert raw, f"{mode} 内置预设不应为空"


def test_preset_keys_define_the_event_vocabulary():
    vocab = set(phrase_keys())
    assert vocab, "事件词表不应为空（由内置预设文件驱动）"
    for mode in BUILTIN_MODES:
        keys = set(_read_preset_file(mode))
        assert keys == vocab, f"{mode} 预设键必须与事件词表完全一致"


def test_loader_snapshot_and_reload_are_idempotent():
    snap = load_builtin_presets()
    assert set(snap) == set(BUILTIN_MODES)
    assert reload_builtin_presets() == snap


def test_picker_renders_builtin_preset_and_rotates_variants():
    picker = PhrasePicker()
    for mode in BUILTIN_MODES:
        first = picker.get(mode, "thinking", "回退", name="DSH")
        assert first != "回退", f"{mode} 应命中预设 thinking 文案"
        assert "DSH" in first
        # 同一 key 轮换：再次取不得重复首句
        assert picker.get(mode, "thinking", "回退", name="DSH") != first


def test_picker_unknown_mode_or_missing_key_returns_fallback():
    picker = PhrasePicker()
    assert picker.get("no_such_mode", "start", "回退", name="X") == "回退"
    assert picker.get("legacy", "no_such_event", "回退") == "回退"


def test_default_phrases_prefer_legacy_first_variant():
    from pet.persona_phrases import default_phrases

    defaults = default_phrases()
    assert set(defaults) == set(phrase_keys())
    legacy = builtin_phrases("legacy")
    for key, first in defaults.items():
        variants = legacy.get(key)
        if variants:
            assert first == variants[0]


def test_preset_placeholders_stay_within_the_rendering_contract():
    """预设文案只能使用各事件 PARAMETERS 声明的字段（保证或条件注入）。

    越界字段在运行时永远得不到替换、会原样露出 {xxx}，属数据缺陷。
    """
    from pet.persona_template import PARAMETERS

    pattern = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)(?:[.:\[][^}]*)?\}")
    for mode in BUILTIN_MODES:
        data = _read_preset_file(mode)
        for key, lines in data.items():
            used = {
                match.group(1)
                for line in (lines if isinstance(lines, list) else [lines])
                for match in pattern.finditer(line)
            }
            allowed = set(PARAMETERS.get(key, ()))
            assert used <= allowed, (mode, key, sorted(used - allowed))
