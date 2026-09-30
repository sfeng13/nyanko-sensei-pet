# -*- coding: utf-8 -*-
from pet.config import Config


def test_dialogue_modes_and_custom_phrases_persist(tmp_path):
    cfg = Config(base=tmp_path)
    assert cfg.get("dialogue_mode") == "legacy"
    cfg.set("dialogue_mode", "whale_maid")
    cfg.set("dialogue_phrases", {"start": "你好", "thinking": ["想想"]})
    cfg.save()
    loaded = Config(base=tmp_path)
    assert loaded.get("dialogue_mode") == "whale_maid"
    assert loaded.get("dialogue_phrases")["start"] == "你好"
    assert loaded.get("dialogue_phrases")["thinking"] == ["想想"]


def test_bad_mode_and_phrase_types_are_repaired(tmp_path):
    cfg = Config(base=tmp_path)
    cfg.set("dialogue_mode", "bad")
    cfg.set("dialogue_phrases", {"start": 42, "thinking": [], "unknown": ["ok"]})
    cfg._normalize_pet_settings()
    assert cfg.get("dialogue_mode") == "legacy"
    assert "start" not in cfg.get("dialogue_phrases")
    assert cfg.get("dialogue_phrases")["unknown"] == ["ok"]


def test_unified_preset_phrases_survive_normalize(tmp_path):
    """双层统一预设 {global, agents} 在 config 清洗后原样保留（ticket 05）。

    旧清洗逻辑只认 {event: [...]} 单层，会把 global/agents 这两个 dict 值
    当作非法条目丢掉；升级后须保留结构且逐事件校验值类型。
    """
    cfg = Config(base=tmp_path)
    preset = {
        "global": {
            "start": ["全局开始"],
            "thinking": ["全局思考"],
        },
        "agents": {
            "dsh": {"start": ["DSH 专属开始"]},
            "claude": {"thinking": 42},  # 非法值须被清掉，但结构保留
        },
    }
    cfg.set("dialogue_phrases", preset)
    cfg._normalize_pet_settings()
    cleaned = cfg.get("dialogue_phrases")
    assert isinstance(cleaned.get("global"), dict)
    assert cleaned["global"]["start"] == ["全局开始"]
    assert isinstance(cleaned.get("agents"), dict)
    assert cleaned["agents"]["dsh"]["start"] == ["DSH 专属开始"]
    # claude 仅含非法 42 → 该 agent 无任何有效覆盖，整键被清理（delta 空无意义）
    assert "claude" not in cleaned["agents"]


# --- ticket 02：统一预设（global + agents delta）渲染路由 ---

def test_phrase_lookup_prefers_agent_delta_over_global():
    """agents[agent_key][key] 优先于 global[key]；缺省回退 global；global 缺失返回 None。"""
    from pet.persona_phrases import phrase_for_agent

    preset = {
        "global": {
            "start": ["全局 start"],
            "thinking": ["全局 thinking"],
        },
        "agents": {
            "dsh": {"start": ["DSH start"]},
        },
    }
    assert phrase_for_agent(preset, "dsh", "start") == ["DSH start"]
    assert phrase_for_agent(preset, "dsh", "thinking") == ["全局 thinking"]
    assert phrase_for_agent(preset, "claude", "start") == ["全局 start"]
    assert phrase_for_agent(preset, "claude", "missing_event") is None


def test_phrase_lookup_accepts_flat_legacy_phrases():
    """旧单层 {key: [...]} 视为 global（preset 无 global 键时整包即 global）。"""
    from pet.persona_phrases import phrase_for_agent

    flat = {"start": ["旧 start"], "thinking": ["旧 thinking"]}
    assert phrase_for_agent(flat, "dsh", "start") == ["旧 start"]
    assert phrase_for_agent(flat, "claude", "thinking") == ["旧 thinking"]


def test_phrase_lookup_non_agent_only_reads_global():
    """非 Agent 场景（agent_key=""）绝不查 agents 层，只查 global。

    非 Agent 事件（self_talk/balance.* 等）只应存在于 global；运行时它们由
    agent_key="" 的调用点渲染，天然绕过 agents 层。agents 层误存非 Agent 事件
    由 UI/导入层约束（ticket 04），不在渲染层维护事件分类。
    """
    from pet.persona_phrases import phrase_for_agent

    preset = {
        "global": {"self_talk": ["只有 global"]},
        "agents": {"dsh": {"start": ["DSH start"]}},
    }
    assert phrase_for_agent(preset, "", "self_talk") == ["只有 global"]


# --- ticket 05：PhrasePicker 的 agent 维度渲染（custom 分支） ---

def test_picker_custom_for_agent_renders_delta_then_global():
    """custom_for_agent：agents[agent_key][key] → global[key] → fallback；
    渲染占位符注入 values。"""
    from pet.persona_phrases import PhrasePicker

    picker = PhrasePicker()
    preset = {
        "global": {
            "start": ["全局 {name} start"],
            "thinking": ["全局 thinking"],
        },
        "agents": {
            "dsh": {"start": ["DSH {name} start"]},
        },
    }
    assert picker.custom_for_agent(preset, "dsh", "start", "fb", name="DSH") == "DSH DSH start"
    assert picker.custom_for_agent(preset, "claude", "start", "fb", name="Claude Code") == "全局 Claude Code start"
    assert picker.custom_for_agent(preset, "claude", "thinking", "fb") == "全局 thinking"
    assert picker.custom_for_agent(preset, "claude", "no_such_event", "回退") == "回退"


def test_picker_custom_for_agent_non_agent_ignores_agents():
    """agent_key=""（非 Agent 场景）只渲染 global，忽略 agents 层。"""
    from pet.persona_phrases import PhrasePicker

    picker = PhrasePicker()
    preset = {
        "global": {"self_talk": ["global 自说自话"]},
        "agents": {"dsh": {"self_talk": ["不该命中"]}},
    }
    assert picker.custom_for_agent(preset, "", "self_talk", "fb") == "global 自说自话"
