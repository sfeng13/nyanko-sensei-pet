import sys
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
from nyanko_games import FORTUNES, NumberGame, daily_fortune, draw_option, play_rps, random_fortune  # noqa: E402


def test_daily_fortune_is_stable():
    day = date(2026, 10, 9)
    assert daily_fortune(day) == daily_fortune(day)
    assert "10月09日" in daily_fortune(day)


def test_fortune_pool_contains_requested_ranks_and_reroll_excludes_previous():
    from collections import Counter
    ranks = Counter(title for title, text in FORTUNES)
    assert set(ranks) == {"大大吉", "大吉", "中吉", "小吉", "吉", "末吉", "平", "凶", "大凶", "大大凶"}
    assert set(ranks.values()) == {3}
    day = date(2026, 10, 9)
    previous = daily_fortune(day)
    rng = Mock()
    rng.choice.side_effect = lambda pool: pool[0]
    assert random_fortune(day, previous, rng) != previous
    assert previous not in rng.choice.call_args.args[0]


def test_draw_rejects_empty_or_duplicate_only_pool():
    for text in ("", "面条\n面条\n "):
        with pytest.raises(ValueError):
            draw_option(text)


def test_custom_draw_normalizes_candidates():
    rng = Mock()
    rng.choice.side_effect = lambda choices: choices[-1]
    assert draw_option(" 面条 \n\n米饭\n面条", rng) == "米饭"
    rng.choice.assert_called_once_with(["面条", "米饭"])


@pytest.mark.parametrize("player,teacher,verdict", [
    ("石头", "剪刀", "你赢了"), ("剪刀", "布", "你赢了"), ("布", "石头", "你赢了"),
    ("石头", "布", "老师赢了"), ("石头", "石头", "平手"),
])
def test_rps_outcomes(player, teacher, verdict):
    assert verdict in play_rps(player, Mock(choice=Mock(return_value=teacher)))


def test_number_game_limits_attempts_and_reveals_answer():
    game = NumberGame(Mock(randint=Mock(return_value=77)))
    with pytest.raises(ValueError):
        game.guess(0)
    assert game.attempts == 0
    assert "偏小" in game.guess(50)
    assert "偏大" in game.guess(90)
    for _ in range(5):
        result = game.guess(1)
    assert game.finished and "77" in result
    game.guess(77)
    assert game.attempts == 7


def test_number_game_success():
    game = NumberGame(Mock(randint=Mock(return_value=42)))
    assert "猜中了" in game.guess(42)
    assert game.finished


def test_menu_opens_games_and_result_can_reach_pet(tmp_path, monkeypatch):
    from PySide6.QtCore import QRect
    from PySide6.QtTest import QSignalSpy
    from PySide6.QtWidgets import QApplication, QMenu, QWidget
    from nyanko_games_ui import add_games_menu
    monkeypatch.setattr("nyanko_paths.user_data_dir", lambda: tmp_path)

    app = QApplication.instance() or QApplication([])
    host = QWidget()
    host.visible_content_rect = lambda: QRect(250, 350, 120, 160)
    host.show()
    menu = QMenu(host)
    menu.addAction("Codex 联动")
    menu.addAction("播放动画")
    games = add_games_menu(menu, host)
    assert [a.text() for a in menu.actions()] == ["Codex 联动", "互动游戏", "播放动画"]
    assert len(games.actions()) == 9
    games.actions()[0].trigger()
    controller = host._nyanko_games_controller
    assert controller.dialog is None
    bubble = controller.bubble
    assert bubble.isVisible()
    fortune = bubble.label.text()
    assert 10000 <= bubble._hide_timer.interval() <= 60000
    assert bubble.geometry().bottom() < host.visible_content_rect().top()
    assert bubble.tail_direction == "down"
    games.actions()[0].trigger()
    assert bubble.label.text() != fortune
    games.actions()[3].menu().actions()[0].trigger()
    assert "你：石头" in bubble.label.text()
    games.actions()[-1].trigger()
    dialog = host._nyanko_games_dialog
    dialog.play_button.click()
    fortune = dialog.result.text()
    dialog.reroll_button.click()
    assert dialog.result.text() != fortune
    dialog.play_button.click()
    assert dialog.result.text() == fortune
    dialog.tell_button.click()
    assert bubble.label.text() == fortune
    games.actions()[-1].trigger()
    assert host._nyanko_games_dialog is dialog
    dialog.mode.setCurrentIndex(1)
    dialog.options.setPlainText("饺子")
    dialog.play_button.click()
    assert not dialog.tell_button.isEnabled()
    dialog.mode.setCurrentIndex(4)
    dialog._number_game.target = 50
    dialog.number.setValue(50)
    dialog.play_button.click()
    assert not dialog.play_button.isEnabled()
    dialog.reset_button.click()
    assert dialog.play_button.isEnabled()
    spy = QSignalSpy(bubble.hidden)
    bubble._hide_timer.start(1)
    assert spy.wait(1000)
    assert not bubble.isVisible()
    host.close()
    app.processEvents()


def test_result_duration_is_bounded_and_grows_with_text():
    from nyanko_game_bubble import result_duration_ms
    assert result_duration_ms("正面") == 10000
    assert result_duration_ms("签文" * 50) > 10000
    assert result_duration_ms("长" * 500) == 60000


def test_custom_food_and_draw_survive_dialog_and_controller_restart(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QWidget
    from nyanko_games_ui import GamesController
    monkeypatch.setattr("nyanko_paths.user_data_dir", lambda: tmp_path)
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    controller = GamesController(host)
    controller.open_dialog()
    dialog = controller.dialog
    dialog.mode.setCurrentIndex(1)
    food = "黄焖鸡\n螺蛳粉\n肠粉"
    dialog.options.setPlainText(food)
    dialog.close()  # No draw or mode switch required to save.
    restarted = GamesController(QWidget())
    assert restarted.pool("food") == food
    restarted.open_dialog()
    restarted.dialog.mode.setCurrentIndex(1)
    assert restarted.dialog.options.toPlainText() == food
    restarted.dialog.mode.setCurrentIndex(2)
    restarted.dialog.options.setPlainText("看书\n散步")
    assert GamesController(QWidget()).pool("draw") == "看书\n散步"
    restarted.dialog.options.clear()
    assert GamesController(QWidget()).pool("draw") == ""
    host.close()
    restarted.host.close()
    app.processEvents()


def test_pool_store_preserves_corrupt_file_and_atomic_save_failure(tmp_path, monkeypatch):
    import json
    import os
    from nyanko_games import GamePools
    path = tmp_path / "games.json"
    path.write_text("broken old data", encoding="utf-8")
    store = GamePools(path)
    store.update("food", "烧麦\n馄饨")
    assert next(tmp_path.glob("games.json.corrupt-*")).read_text(encoding="utf-8") == "broken old data"
    original = path.read_text(encoding="utf-8")
    assert json.loads(original)["pools"]["food"] == "烧麦\n馄饨"
    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", Mock(side_effect=PermissionError("read only")))
        with pytest.raises(PermissionError):
            store.update("food", "米粉\n凉皮")
    assert path.read_text(encoding="utf-8") == original
    assert not list(tmp_path.glob("*.tmp"))
    store.update("food", "米粉\n凉皮")
    assert GamePools(path).values["food"] == "米粉\n凉皮"


def test_pool_defaults_and_unknown_fields_are_preserved(tmp_path):
    import json
    from nyanko_games import FOODS, GamePools
    path = tmp_path / "含空格 中文目录" / "games.json"
    assert GamePools(path).values["food"] == "\n".join(FOODS)
    path.parent.mkdir()
    path.write_text(json.dumps({"version": 1, "future": True, "pools": {"other": "保留"}}), encoding="utf-8")
    GamePools(path).update("food", "酸菜鱼\n小炒肉")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["future"] and data["pools"]["other"] == "保留"


def test_dialog_reports_save_failure_and_retry(tmp_path, monkeypatch):
    import os
    from PySide6.QtWidgets import QApplication
    from nyanko_games import GamePools
    from nyanko_games_ui import GamesDialog
    app = QApplication.instance() or QApplication([])
    store = GamePools(tmp_path / "games.json")
    dialog = GamesDialog(pool_store=store)
    dialog.open_game("food")
    with monkeypatch.context() as patch:
        patch.setattr(os, "replace", Mock(side_effect=PermissionError("read only")))
        dialog.options.setPlainText("炒米粉\n烧腊")
    assert "保存失败" in dialog.hint.text()
    assert dialog.options.toPlainText() == "炒米粉\n烧腊"
    dialog.options.setPlainText("炒米粉\n烧腊\n煲仔饭")
    assert "自动保存" in dialog.hint.text()
    assert GamePools(store.path).values["food"] == "炒米粉\n烧腊\n煲仔饭"
    dialog.close()
    app.processEvents()
