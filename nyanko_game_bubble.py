"""Transient game result, anchored to the pet with an inward pointing tail."""
from PySide6.QtCore import QRect, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QWidget
from pet.speech_bubble_text import bubble_rect_for_anchor, bubble_tail_direction


def result_duration_ms(text):
    return max(10000, min(60000, 10000 + max(0, len(text.strip()) - 30) * 250))


class GameResultBubble(QWidget):
    hidden = Signal()

    def __init__(self, host):
        super().__init__(host)
        self.host = host
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color: #403725; background: transparent;")
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self.tail_direction = "down"
        listener = getattr(host, "add_position_listener", None)
        if callable(listener):
            listener(self.follow_pet)

    def show_result(self, text):
        self._hide_timer.stop()
        metrics = QFontMetrics(self.label.font())
        text = str(text)[:500]
        width = max(150, min(320, max(metrics.horizontalAdvance(line) for line in text.splitlines() or [""])))
        bounds = metrics.boundingRect(QRect(0, 0, width, 1000), Qt.TextFlag.TextWordWrap, text)
        self.label.setText(text)
        self.label.setGeometry(16, 16, width + 2, max(24, bounds.height() + 4))
        self.resize(width + 34, self.label.height() + 38)
        self._place()
        self.show()
        self.raise_()
        self._hide_timer.start(result_duration_ms(text))

    def follow_pet(self, *args):
        if self.isVisible():
            self._place()

    def _place(self):
        anchor = self.host.visible_content_rect()
        screen = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        rect = bubble_rect_for_anchor(anchor, self.size(), screen.availableGeometry(), "top")
        self.move(rect.topLeft())
        self.tail_direction = bubble_tail_direction(anchor, rect)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        body = self.rect().adjusted(3, 10, -3, -10)
        path = QPainterPath()
        path.addRoundedRect(body, 14, 14)
        anchor = self.mapFromGlobal(self.host.visible_content_rect().center())
        x = max(24, min(self.width() - 24, anchor.x()))
        y = max(24, min(self.height() - 24, anchor.y()))
        if self.tail_direction == "down":
            points = ((x-7, body.bottom()-1), (x, self.height()-2), (x+7, body.bottom()-1))
        elif self.tail_direction == "up":
            points = ((x-7, body.top()+1), (x, 2), (x+7, body.top()+1))
        elif self.tail_direction == "left":
            points = ((body.left()+1, y-7), (0, y), (body.left()+1, y+7))
        else:
            points = ((body.right()-1, y-7), (self.width()-1, y), (body.right()-1, y+7))
        tail = QPainterPath()
        tail.moveTo(QPointF(*points[0]))
        for point in points[1:]:
            tail.lineTo(QPointF(*point))
        tail.closeSubpath()
        painter.setPen(QPen(QColor("#efc261"), 1))
        painter.setBrush(QColor("#fffaf0"))
        painter.drawPath(path.united(tail))

    def hideEvent(self, event):
        self._hide_timer.stop()
        self.hidden.emit()
        super().hideEvent(event)
