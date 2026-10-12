"""Role adaptation must retain settings and Agent animation contracts."""
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from nyanko_choreography import ALERT, CLICK, IDLE, LECTURE, NAP, ROUTINES, SNACK, STRETCH, PUBLIC  # noqa: E402
from nyanko_runtime import NyankoWindow  # noqa: E402
from pet.config import Config  # noqa: E402
from pet.agent_link import AgentLinkManager  # noqa: E402
from pet.library import MovieLibrary  # noqa: E402
from pet.modern_settings_dialog import ModernSettingsDialog  # noqa: E402


@pytest.fixture
def pet(tmp_path):
    app = QApplication.instance() or QApplication([])
    cfg = Config(base=tmp_path)
    cfg.set('character', 'nyanko-sensei')
    lib = MovieLibrary(
        character_id='nyanko-sensei', prewarm_enabled=False,
        asset_dir=Path(__file__).resolve().parents[2] / 'characters/nyanko-sensei/videos',
    )
    win = NyankoWindow(lib, cfg)
    yield win
    win.close()
    lib.shutdown()
    app.processEvents()


def finish_routine(pet, target=IDLE):
    for _ in range(12):
        pet._on_anim_ended(pet.anim)
        if pet.anim == target:
            return
    pytest.fail('routine did not return to idle')


def test_agent_category_contains_only_playable_public_actions(pet):
    assert pet.cats['acts'] == pet.acts
    assert set(pet.cats['acts']) <= set(PUBLIC)


def test_agent_work_has_character_specific_rotation(pet):
    manager = AgentLinkManager(pet, pet.cfg)
    try:
        assert [manager._next_link_anim_rotation() for _ in range(3)] == [ALERT, LECTURE, STRETCH]
    finally:
        manager.shutdown()


def test_action_gap_waits_after_complete_routine_without_breaking_phases(pet):
    pet.cfg.set('animation_gap_seconds', 12)
    pet.refresh_pet_settings()
    pet._switch(SNACK)
    pet._on_anim_ended(SNACK)
    assert pet.anim == ROUTINES[SNACK][1]
    assert not pet._animation_gap_active
    finish_routine(pet)
    assert pet._animation_gap_active
    assert pet._animation_gap_timer.isActive()
    pet._calm_cycles = pet._idle_target
    pet._on_anim_ended(IDLE)
    assert pet.anim == IDLE


def test_queued_agent_request_waits_for_routine_exit_then_plays(pet):
    pet._switch(NAP)
    pet.request_link_anim(LECTURE)
    assert pet.anim == NAP
    pet._on_anim_ended(NAP)
    assert pet.anim == ROUTINES[NAP][1]
    finish_routine(pet, target=LECTURE)
    assert pet.anim == LECTURE


def test_busy_agent_chains_next_action_and_idle_cancels_queue(pet):
    pet.request_link_anim(LECTURE)
    pet.set_link_next_provider(lambda: ALERT)
    pet._on_anim_ended(LECTURE)
    assert pet.anim == ALERT
    pet.request_link_anim(SNACK)
    pet.request_link_idle()
    pet._on_anim_ended(ALERT)
    assert pet.anim == IDLE


def test_explicit_click_is_not_delayed_by_automatic_action_gap(pet):
    pet.cfg.set('animation_gap_seconds', 12)
    pet.refresh_pet_settings()
    pet._switch(LECTURE)
    pet._on_anim_ended(LECTURE)
    pet._switch(CLICK)
    assert pet.anim == CLICK
    assert not pet._animation_gap_active
    pet._on_anim_ended(CLICK)
    assert pet.anim == IDLE
    assert not pet._animation_gap_active


def test_agent_request_during_internal_phase_is_queued(pet):
    pet._switch(NAP)
    pet._on_anim_ended(NAP)
    assert pet.anim == ROUTINES[NAP][1]
    pet.request_link_anim(LECTURE)
    assert pet.anim == ROUTINES[NAP][1]
    finish_routine(pet, target=LECTURE)


def test_settings_round_trip_reaches_character_window(pet):
    dialog = ModernSettingsDialog(pet.cfg, pet, include_ai=False)
    dialog.no_move_check.setChecked(True)
    dialog.lock_position_check.setChecked(True)
    dialog.click_self_talk_check.setChecked(True)
    dialog.self_talk_check.setChecked(True)
    dialog.texts_edit.setPlainText('老师，该吃团子了')
    dialog.gap_spin.setValue(9)
    dialog.speed_select.setCurrentData(1.5)
    dialog.close()  # The actual settings close/save path, not a config stub.
    pet.cfg.reload()
    pet.refresh_pet_settings()
    assert pet.no_move and pet.lock_position
    assert not pet._can_roam()
    assert pet.click_show_self_talk and pet._self_talk_enabled
    assert pet._self_talk_texts == ['老师，该吃团子了']
    assert pet.animation_gap_seconds == 9
    assert pet.playback_speed == 1.5
    reloaded = Config(base=pet.cfg.dir.parent)
    assert reloaded.get('animation_gap_seconds') == 9
    assert reloaded.get('self_talk_texts') == ['老师，该吃团子了']


def test_missing_singing_asset_is_explained_and_existing_preference_retained(pet):
    pet.cfg.set('music_sing_enabled', True)
    pet.refresh_pet_settings()
    dialog = ModernSettingsDialog(pet.cfg, pet, include_ai=False)
    assert not dialog.music_sing_check.isEnabled()
    assert '素材' in dialog.music_sing_check.toolTip()
    assert not pet._music_sing_timer.isActive()
    dialog.close()
    assert pet.cfg.get('music_sing_enabled') is True
