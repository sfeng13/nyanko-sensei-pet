"""A modeless, keyboard-accessible game window for the desktop companion."""
import random
import shiboken6
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QTextEdit, QVBoxLayout, QInputDialog,
)
from nyanko_games import GAMES, GamePools, NumberGame, daily_fortune, draw_option, play_rps, random_fortune


class GamesController:
    def __init__(self, host):
        self.host = host
        self.dialog = None
        self.bubble = None
        self.number_game = None
        self.previous_fortune = None
        self.pool_store = GamePools()

    def present(self, text):
        from nyanko_game_bubble import GameResultBubble
        # Remove only an old game alert created by the previous sticky path.
        current = getattr(self.host, "_alert_current", None)
        if current and current.get("alertType") == "game":
            self.host.hide_bubble()
        if self.bubble is None or not shiboken6.isValid(self.bubble):
            self.bubble = GameResultBubble(self.host)
        self.bubble.show_result(text)

    def pool(self, key):
        if self.dialog is not None and shiboken6.isValid(self.dialog):
            if self.dialog.mode.currentData() == key:
                return self.dialog.options.toPlainText()
            return self.dialog._pools[key]
        return self.pool_store.values[key]

    def play(self, key, move=None):
        try:
            if key == "fortune":
                text = random_fortune(previous=self.previous_fortune)
                self.previous_fortune = text
            elif key in ("food", "draw"):
                text = ("今天吃：" if key == "food" else "抽中了：") + draw_option(self.pool(key))
            elif key == "rps":
                text = play_rps(move)
            elif key == "coin":
                text = "硬币落下：" + random.choice(("正面", "反面"))
            elif key == "dice":
                text = f"掷出了 {random.randint(1, 6)} 点！"
            else:
                return self.guess_number()
        except ValueError as error:
            text = str(error)
        self.present(text)

    def new_number_game(self):
        self.number_game = NumberGame()
        self.present("老师藏了一个 1～100 的整数。\n右键 → 互动游戏 → 猜数字 → 猜一个数字。你有七次机会！")

    def guess_number(self):
        if self.number_game is None or self.number_game.finished:
            self.number_game = NumberGame()
        number, accepted = QInputDialog.getInt(self.host, "猜数字", "老师藏了 1～100 的整数。你猜多少？", 50, 1, 100)
        if accepted:
            self.present(self.number_game.guess(number))

    def open_dialog(self):
        if self.dialog is None or not shiboken6.isValid(self.dialog):
            self.dialog = GamesDialog(self.host, pool_store=self.pool_store)
            self.dialog.result_requested.connect(self.present)
            self.host._nyanko_games_dialog = self.dialog
        self.dialog.open_game("fortune")


def add_games_menu(menu, host):
    from pet.context_menus.shared import add_action, add_submenu

    games_menu = add_submenu(menu, "互动游戏")
    menu.removeAction(games_menu.menuAction())
    before = next((action for action in menu.actions() if action.text().strip() == "播放动画"), None)
    if before:
        menu.insertMenu(before, games_menu)
    else:
        menu.addMenu(games_menu)

    controller = getattr(host, "_nyanko_games_controller", None)
    if controller is None:
        controller = GamesController(host)
        host._nyanko_games_controller = controller
    for key, title in GAMES.items():
        if key == "rps":
            choices = add_submenu(games_menu, title)
            for move in ("石头", "剪刀", "布"):
                add_action(choices, move, None, lambda move=move: controller.play("rps", move), close_on_trigger=True)
        elif key == "guess":
            choices = add_submenu(games_menu, title)
            add_action(choices, "猜一个数字…", None, controller.guess_number, close_on_trigger=True)
            add_action(choices, "开始新一局", None, controller.new_number_game, close_on_trigger=True)
        else:
            add_action(games_menu, title, None, lambda key=key: controller.play(key), close_on_trigger=True)
    games_menu.addSeparator()
    add_action(games_menu, "打开互动游戏界面…", None, controller.open_dialog, close_on_trigger=True)
    return games_menu


class GamesDialog(QDialog):
    result_requested = Signal(str)

    def __init__(self, parent=None, *, pool_store=None):
        super().__init__(parent)
        self.setWindowTitle("猫咪老师 · 互动游戏")
        self.setMinimumWidth(380)
        self.resize(430, 470)
        self.setStyleSheet("""
            QDialog { background: #24252a; color: #f5f5f5; }
            QLabel { color: #f5f5f5; }
            QLabel#gameHint { color: #bfc1ca; }
            QLabel#gameResult { background: #30323a; border: 1px solid #474a55;
                border-radius: 12px; padding: 18px; font-size: 16px; }
            QComboBox, QTextEdit, QSpinBox { background: #30323a; color: #f5f5f5;
                border: 1px solid #5c606d; border-radius: 6px; padding: 7px; }
            QComboBox QAbstractItemView { background: #30323a; color: #f5f5f5;
                selection-background-color: #735238; }
            QPushButton { background: #3b3e47; color: #f5f5f5; padding: 9px 14px;
                border: 1px solid #5c606d; border-radius: 7px; }
            QPushButton:hover { background: #505460; }
            QPushButton:focus { border: 2px solid #e8b789; }
            QPushButton:disabled { color: #8f929b; background: #30323a; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        title = QLabel("陪猫咪老师玩一会儿")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)
        self.mode = QComboBox()
        self.mode.setAccessibleName("选择小游戏")
        for key, label in GAMES.items():
            self.mode.addItem(label, key)
        layout.addWidget(self.mode)
        self.hint = QLabel()
        self.hint.setObjectName("gameHint")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.options = QTextEdit()
        self.options.setAccessibleName("抽签候选项，每行一个")
        self.options.setPlaceholderText("每行一个选项，至少两个不同选项")
        self.options.setMaximumHeight(130)
        layout.addWidget(self.options)
        self.number = QSpinBox()
        self.number.setRange(1, 100)
        self.number.setValue(50)
        self.number.setAccessibleName("你猜的数字")
        layout.addWidget(self.number)
        self.rps_row = QHBoxLayout()
        self.rps_buttons = []
        for move in ("石头", "剪刀", "布"):
            button = QPushButton(move)
            button.clicked.connect(lambda checked=False, move=move: self.play(move))
            self.rps_row.addWidget(button)
            self.rps_buttons.append(button)
        layout.addLayout(self.rps_row)
        self.result = QLabel("选好以后开始吧。")
        self.result.setObjectName("gameResult")
        self.result.setWordWrap(True)
        self.result.setMinimumHeight(110)
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.result, 1)
        controls = QHBoxLayout()
        self.play_button = QPushButton("抽一签")
        self.play_button.clicked.connect(lambda: self.play())
        self.reset_button = QPushButton("新一局")
        self.reset_button.clicked.connect(self.reset_number)
        self.reroll_button = QPushButton("再抽一签")
        self.reroll_button.clicked.connect(lambda: self.play(reroll=True))
        self._last_fortune = None
        controls.addWidget(self.play_button)
        controls.addWidget(self.reset_button)
        controls.addWidget(self.reroll_button)
        layout.addLayout(controls)
        self.tell_button = QPushButton("让猫咪老师说结果")
        self.tell_button.setEnabled(False)
        self.tell_button.clicked.connect(self.tell_result)
        layout.addWidget(self.tell_button)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)
        self.pool_store = pool_store if pool_store is not None else GamePools()
        self._pools = self.pool_store.values
        self._previous = None
        self.mode.currentIndexChanged.connect(self._change_mode)
        self._change_mode()
        self.options.textChanged.connect(self._save_pool)

    def _save_pool(self):
        key = self.mode.currentData()
        if key not in self._pools:
            return
        try:
            self.pool_store.update(key, self.options.toPlainText())
        except OSError:
            self.hint.setText("保存失败：请检查用户数据目录是否可写。当前内容仍保留在窗口中；重新编辑会再次尝试保存。")
        else:
            self.hint.setText("每行一个选项。修改会自动保存，关闭窗口或重启桌宠后仍保留。")

    def open_game(self, key):
        self.mode.setCurrentIndex(list(GAMES).index(key))
        self.show()
        self.raise_()
        self.activateWindow()

    def _change_mode(self):
        if self._previous in self._pools:
            self._pools[self._previous] = self.options.toPlainText()
        key = self.mode.currentData()
        self._previous = key
        self.options.setVisible(key in self._pools)
        if key in self._pools:
            was_blocked = self.options.blockSignals(True)
            self.options.setPlainText(self._pools[key])
            self.options.blockSignals(was_blocked)
        self.number.setVisible(key == "guess")
        self.reset_button.setVisible(key == "guess")
        self.reroll_button.setVisible(key == "fortune")
        self.play_button.setVisible(key != "rps")
        for button in self.rps_buttons:
            button.setVisible(key == "rps")
        hints = {
            "fortune": "十档运势、三十条签文。今日签当天固定，再抽一签可以换个结果。",
            "food": "把不想吃的删掉，也可以添加自己的菜名，每行一个。修改自动保存。",
            "draw": "把纠结的选项写下来，老师帮你挑一个。修改自动保存。",
            "rps": "选石头、剪刀或布，老师也会同时出拳。",
            "guess": "老师藏了一个 1～100 的整数，你有七次机会。",
            "coin": "心里先定好正反面的含义，再抛一次。",
            "dice": "一颗六面骰子，点数为 1～6。",
        }
        self.hint.setText(hints[key])
        self.play_button.setText({"fortune": "今日签", "guess": "猜一下", "coin": "抛一次", "dice": "掷一次"}.get(key, "抽一签"))
        self.play_button.setEnabled(True)
        self.tell_button.setEnabled(False)
        self.result.setText("选好以后开始吧。")
        if key == "guess":
            self.reset_number()

    def reset_number(self):
        self._number_game = NumberGame()
        self.result.setText("老师藏好数字了。你先猜多少？")
        self.number.setEnabled(True)
        self.play_button.setEnabled(True)
        self.tell_button.setEnabled(False)

    def tell_result(self):
        self.hide()
        self.result_requested.emit(self.result.text())

    def play(self, move=None, *, reroll=False):
        key = self.mode.currentData()
        try:
            if key == "fortune":
                text = random_fortune(previous=self._last_fortune) if reroll else daily_fortune()
                self._last_fortune = text
            elif key in ("food", "draw"):
                text = ("今天吃：" if key == "food" else "抽中了：") + draw_option(self.options.toPlainText())
            elif key == "rps":
                text = play_rps(move)
            elif key == "guess":
                text = self._number_game.guess(self.number.value())
                self.play_button.setEnabled(not self._number_game.finished)
                self.number.setEnabled(not self._number_game.finished)
            elif key == "coin":
                text = "硬币落下：" + random.choice(("正面", "反面"))
            else:
                text = f"掷出了 {random.randint(1, 6)} 点！"
        except ValueError as error:
            self.result.setText(str(error))
            self.tell_button.setEnabled(False)
            return
        self.result.setText(text)
        self.tell_button.setEnabled(True)
