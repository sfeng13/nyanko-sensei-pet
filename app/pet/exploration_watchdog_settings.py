# -*- coding: utf-8 -*-
"""Agent Exploration Loop Watchdog settings page.

Used by the modern settings dialog as a sidebar page.

Configuration keys live under the `agent_link` sub-dict:

    agent_link.exploration_watchdog_enabled
    agent_link.exploration_watchdog_warning_threshold
    agent_link.exploration_watchdog_control_threshold
    agent_link.exploration_watchdog_cooldown_steps
    agent_link.exploration_watchdog_early_grace_minutes
    agent_link.exploration_watchdog_long_run_minutes
    agent_link.exploration_watchdog_long_think_seconds
"""
from __future__ import annotations

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from .modern_settings_dialog import (
    BrowserSpinBox,
    SettingRow,
    SettingsSection,
    ToggleSwitch,
)

log = logging.getLogger("dsh-pet-standalone")


class WatchdogSettingsPage(QWidget):
    """Self-contained settings page for Agent Exploration Loop Watchdog.

    Organised in three sections:
      1. 基础设置 (enable toggle)
      2. 风险评分 (warning / control thresholds)
      3. Think 风控 (cooldown, grace, long-run)
    """

    settings_saved = Signal()

    def __init__(self, config, agent_link_cfg: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.config = config
        self._agent_cfg = dict(agent_link_cfg)

        # ---- 基础设置 ----
        self.enabled_check = ToggleSwitch(self)
        self.enabled_check.setChecked(bool(self._agent_cfg.get("exploration_watchdog_enabled", True)))

        # ---- 风险评分 ----
        self.warning_spin = BrowserSpinBox(self)
        self.warning_spin.setRange(1, 20)
        self.warning_spin.setSuffix(" 分")
        self.warning_spin.setValue(int(self._agent_cfg.get("exploration_watchdog_warning_threshold", 3)))
        self.control_spin = BrowserSpinBox(self)
        self.control_spin.setRange(1, 30)
        self.control_spin.setSuffix(" 分")
        self.control_spin.setValue(int(self._agent_cfg.get("exploration_watchdog_control_threshold", 5)))

        # ---- Think 风控 ----
        self.cooldown_spin = BrowserSpinBox(self)
        self.cooldown_spin.setRange(1, 20)
        self.cooldown_spin.setSuffix(" 步")
        self.cooldown_spin.setValue(int(self._agent_cfg.get("exploration_watchdog_cooldown_steps", 3)))
        self.grace_spin = BrowserSpinBox(self)
        self.grace_spin.setRange(1, 30)
        self.grace_spin.setSuffix(" 分钟")
        self.grace_spin.setValue(int(self._agent_cfg.get("exploration_watchdog_early_grace_minutes", 5)))
        self.long_run_spin = BrowserSpinBox(self)
        self.long_run_spin.setRange(2, 240)
        self.long_run_spin.setSuffix(" 分钟")
        self.long_run_spin.setValue(int(self._agent_cfg.get("exploration_watchdog_long_run_minutes", 10)))

        # ---- Layout ----
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(18)

        root.addWidget(SettingsSection("基础设置", [
            SettingRow("watchdog_enabled", "启用循环检测",
                        "识别重复的 Search/Read/Think 行为，防止 Agent 陷入无限探索循环。",
                        self.enabled_check),
        ], self))

        root.addWidget(SettingsSection("风险评分", [
            SettingRow("warning_threshold", "Warning 阈值",
                        "风险分数达到此值时发出警告提醒。", self.warning_spin),
            SettingRow("control_threshold", "Control 阈值",
                        "风险分数达到此值时发出高级别警告提醒。", self.control_spin),
        ], self))

        root.addWidget(SettingsSection("Think 风控", [
            SettingRow("cooldown_steps", "评估冷却步数",
                        "两次风险检测之间的最小步数间隔，防止高频误报。", self.cooldown_spin),
            SettingRow("early_grace_minutes", "启动宽限期",
                        "Agent 启动后的前 N 分钟提高风险阈值，允许更多探索空间。", self.grace_spin),
            SettingRow("long_run_minutes", "长运行降阈值",
                        "连续运行超过 N 分钟后，风险阈值自动降低 1，提高敏感度。", self.long_run_spin),
        ], self))

        root.addStretch(1)

    def apply_to_config(self, agent_link_cfg: dict) -> dict:
        """Merge current values into the agent_link config dict.

        Returns the updated dict for the caller to persist.
        """
        updated = dict(agent_link_cfg)
        updated["exploration_watchdog_enabled"] = self.enabled_check.isChecked()
        updated["exploration_watchdog_warning_threshold"] = self.warning_spin.value()
        updated["exploration_watchdog_control_threshold"] = self.control_spin.value()
        updated["exploration_watchdog_cooldown_steps"] = self.cooldown_spin.value()
        updated["exploration_watchdog_early_grace_minutes"] = self.grace_spin.value()
        updated["exploration_watchdog_long_run_minutes"] = self.long_run_spin.value()
        return updated

    def refresh_from_config(self, agent_link_cfg: dict) -> None:
        """Re-read values from the live config (e.g. after external change)."""
        self._agent_cfg = dict(agent_link_cfg)
        self.enabled_check.setChecked(bool(self._agent_cfg.get("exploration_watchdog_enabled", True)))
        self.warning_spin.setValue(int(self._agent_cfg.get("exploration_watchdog_warning_threshold", 3)))
        self.control_spin.setValue(int(self._agent_cfg.get("exploration_watchdog_control_threshold", 5)))
        self.cooldown_spin.setValue(int(self._agent_cfg.get("exploration_watchdog_cooldown_steps", 3)))
        self.grace_spin.setValue(int(self._agent_cfg.get("exploration_watchdog_early_grace_minutes", 5)))
        self.long_run_spin.setValue(int(self._agent_cfg.get("exploration_watchdog_long_run_minutes", 10)))

