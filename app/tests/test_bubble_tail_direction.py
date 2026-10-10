import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import QApplication, QWidget

from pet.speech_bubble import PetSpeechBubble
from pet.window import PetWindow


class CaptureHost(QWidget):
    set_capture_headroom = PetWindow.set_capture_headroom

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self._capture_headroom = 0
        self._h = 235
        self.setGeometry(300, 400, 250, 235)

    def _apply_scale(self):
        self._h = 235 + self._capture_headroom
        self.setFixedSize(250, self._h)

    def _sync_mask(self):
        pass  # Renderer boundary; the real host's resize/move method is used.

    def visible_content_rect(self):
        return QRect(self.x(), self.y() + self._capture_headroom + 20, 150, 200)


@pytest.mark.parametrize("bubble_rect, side", [
    (QRect(128, 90, 145, 60), "left"),  # Screenshot: a side bubble overlaps the pet by 12px.
    (QRect(-130, 90, 145, 60), "right"),
    (QRect(0, -20, 145, 60), "down"),
    (QRect(0, 210, 145, 60), "up"),
    (QRect(170, 90, 145, 60), "left"),
])
def test_tail_faces_pet_even_when_screen_clamping_causes_overlap(bubble_rect, side):
    from pet.speech_bubble_text import bubble_tail_direction
    assert bubble_tail_direction(QRect(0, 20, 140, 200), bubble_rect) == side


@pytest.mark.parametrize("content", ["text", "image"])
def test_capture_bubble_tail_faces_anchor_for_text_and_images(content, tmp_path):
    app = QApplication.instance() or QApplication([])
    host = QWidget()
    host.setGeometry(100, 100, 250, 235)
    host.show()
    bubble = PetSpeechBubble(host)
    bubble.set_capture_compat(True, host)
    anchor = QRect(100, 120, 150, 200)
    if content == "text":
        bubble.show_text("好模型……", anchor, 3000)
    else:
        image = QPixmap(110, 80)
        image.fill(QColor("#f2c18b"))
        path = tmp_path / "image.png"
        assert image.save(str(path))
        assert bubble.show_image(path, anchor, 3000)
    app.processEvents()
    global_rect = QRect(bubble.mapToGlobal(bubble.rect().topLeft()), bubble.size())
    assert global_rect.intersects(anchor)
    assert global_rect.center().x() > anchor.center().x()
    assert bubble._tail_tip.x() < bubble._surface_rect.left()
    bubble.dismiss()
    host.close()
    app.processEvents()


@pytest.mark.parametrize("content", ["text", "image"])
def test_capture_bubble_reserves_headroom_without_moving_pet(content, tmp_path):
    app = QApplication.instance() or QApplication([])
    host = CaptureHost()
    host.show()
    anchor = host.visible_content_rect()
    bubble = PetSpeechBubble(host)
    bubble.set_capture_compat(True, host)
    if content == "text":
        bubble.show_text("好模型……", anchor, 3000)
    else:
        image = QPixmap(110, 80)
        image.fill(QColor("#f2c18b"))
        path = tmp_path / "headroom-image.png"
        assert image.save(str(path))
        assert bubble.show_image(path, anchor, 3000)
    app.processEvents()
    global_rect = QRect(bubble.mapToGlobal(bubble.rect().topLeft()), bubble.size())
    assert global_rect.bottom() < anchor.top()
    assert host.visible_content_rect() == anchor
    assert host._capture_headroom > 0
    assert bubble._tail_tip.y() > bubble._surface_rect.bottom()
    bubble.dismiss()
    assert host._capture_headroom == 0
    assert host.visible_content_rect() == anchor
    host.close()
    app.processEvents()


def test_capture_at_screen_top_falls_back_without_offscreen_headroom():
    app = QApplication.instance() or QApplication([])
    host = CaptureHost()
    host.move(300, 0)
    host.show()
    bubble = PetSpeechBubble(host)
    bubble.set_capture_compat(True, host)
    bubble.show_text("好模型……", host.visible_content_rect(), 3000)
    assert host._capture_headroom == 0
    assert bubble._tail_tip.x() < bubble._surface_rect.left()
    bubble.dismiss()
    host.close()
    app.processEvents()


def _check_timeout_releases_headroom_but_external_resize_is_preserved():
    from PySide6.QtTest import QSignalSpy
    app = QApplication.instance() or QApplication([])
    host = CaptureHost()
    host.show()
    bubble = PetSpeechBubble(host)
    bubble.set_capture_compat(True, host)
    anchor = host.visible_content_rect()
    bubble.show_text("好模型……", anchor, 3000)
    spy = QSignalSpy(bubble.hidden_signal)
    bubble._hide_timer.start(1)
    assert spy.wait(1000)
    assert host._capture_headroom == 0
    assert host.visible_content_rect() == anchor
    bubble.show_text("再次显示", anchor, 3000)
    host.set_capture_headroom(host._capture_headroom + 20)
    external = host._capture_headroom
    bubble.dismiss()
    assert host._capture_headroom == external
    host.close()
    app.processEvents()


def test_timeout_releases_headroom_but_external_resize_is_preserved():
    import os
    import subprocess
    import sys
    from pathlib import Path
    # A fresh Qt process prevents legacy-suite callbacks from running inside
    # QSignalSpy's nested wait loop against widgets already destroyed by other tests.
    result = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, '.'); "
         "from tests.test_bubble_tail_direction import "
         "_check_timeout_releases_headroom_but_external_resize_is_preserved as check; check()"],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True, timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
