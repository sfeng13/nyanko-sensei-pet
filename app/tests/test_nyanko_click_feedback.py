import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QWidget

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from nyanko_choreography import CLICK, PROTEST, IDLE, Choreography  # noqa: E402
from nyanko_runtime import NyankoWindow  # noqa: E402
from pet.golden_spin import GoldenSpinController  # noqa: E402
from pet.window import PetWindow  # noqa: E402
from pet.window_optional_services import WindowFeatureGateMixin  # noqa: E402


class ClickPet(QWidget, WindowFeatureGateMixin):
    """Real effects/event loop with a renderer-free character animation boundary."""
    _on_click = NyankoWindow._on_click
    _on_anim_ended = NyankoWindow._on_anim_ended
    _schedule_click_sound = PetWindow._schedule_click_sound

    def __init__(self, directory):
        super().__init__()
        self.settings = {"golden_spin_on_click": False, "golden_spin_direct": False}
        self.cfg = SimpleNamespace(dir=directory, get=lambda key, default=None: self.settings.get(key, default))
        self.choreography = Choreography()
        self._just_dragged = False
        self._click_counter = 0
        self.clicks = [CLICK, PROTEST]
        self._edge_probe = None
        self._golden_spin = GoldenSpinController(self)
        self.on_restore_fun_windows = None
        self.click_show_balance = False
        self.on_show_balance = None
        self.click_show_self_talk = True
        self._self_talk_enabled = True
        self._play_click_sound = Mock()
        self._show_click_self_talk = Mock(return_value=True)
        self._schedule_self_talk = Mock()
        self.mark_activity = Mock()
        self._hidden_paused = False
        self._move_plan = None
        self._closing = False

    @property
    def click_sound_enabled(self):
        return self.settings.get("click_sound_enabled", True)

    def _switch(self, name):
        self.choreography.request(name)
        return True

    def _commit(self, candidate, clip):
        self.choreography = candidate
        return True


@pytest.fixture
def click_pet(tmp_path):
    app = QApplication.instance() or QApplication([])
    pet = ClickPet(tmp_path)
    yield pet, app
    pet._golden_spin.cancel()
    pet.close()
    app.processEvents()


def test_character_click_retains_feedback_and_choreography(click_pet):
    pet, app = click_pet
    pet._on_click()
    app.processEvents()
    assert pet.choreography.current == CLICK
    pet._play_click_sound.assert_called_once()
    pet._show_click_self_talk.assert_called_once_with(CLICK)
    pet._schedule_self_talk.assert_called_once_with(after_display=True)
    pet._on_anim_ended(CLICK)
    assert pet.choreography.current == IDLE
    pet._on_click()
    assert pet.choreography.current == PROTEST


def test_disabled_sound_and_speech_are_respected(click_pet):
    pet, app = click_pet
    pet.settings["click_sound_enabled"] = False
    pet.click_show_self_talk = False
    pet._on_click()
    app.processEvents()
    pet._play_click_sound.assert_not_called()
    pet._show_click_self_talk.assert_not_called()


def test_spin_after_character_click_waits_for_real_clip_end(click_pet):
    pet, app = click_pet
    pet.settings["golden_spin_on_click"] = True
    pet._on_click()
    assert pet.choreography.current == CLICK
    assert pet._golden_spin.pending_after_click
    assert not pet._golden_spin.active
    pet._on_anim_ended(PROTEST)  # Ignore an old/out-of-order clip completion.
    assert not pet._golden_spin.active
    pet._on_anim_ended(CLICK)
    assert pet._golden_spin.active
    assert not pet._golden_spin.pending_after_click
    assert pet.choreography.current == IDLE


def test_direct_spin_and_drag_do_not_trigger_character_feedback(click_pet):
    pet, app = click_pet
    pet.settings.update(golden_spin_on_click=True, golden_spin_direct=True)
    pet._just_dragged = True
    pet._on_click()
    assert not pet._golden_spin.active
    pet._just_dragged = False
    pet._on_click()
    assert pet._golden_spin.active
    assert pet.choreography.current == IDLE
    pet._show_click_self_talk.assert_not_called()
    pet._on_click()
    assert pet._golden_spin.queued_turns == 2
