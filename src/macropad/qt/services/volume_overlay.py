from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap, QRegion
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from PIL.ImageQt import ImageQt

from ...core.volume_mixer import VolumeMixerResult
from ...core.windows_icons import extract_file_icon
from ...platform.window_effects import apply_backdrop
from ..app_icon import render_app_icon_pixmap


@dataclass(slots=True)
class OverlayStyle:
    # Hard-coded defaults (edit here to style the overlay).
    bg_color: str = "#282828"
    bg_opacity: int = 220
    backdrop_mode: str = "blur"
    backdrop_opacity: int = 220
    width: int = 190
    height: int = 46
    icon_size: int = 24
    icon_left_padding: int = 8
    title_left_padding: int = 4
    title_y_offset: int = 0
    bar_width: int = 110
    bar_height: int = 4
    bar_left_offset: int = 5
    bar_y_offset: int = -10
    bar_fill_color: str = "#979797"
    bar_bg_color: str = "#848484"
    title_color: str = "#F5F5F5"
    number_color: str = "#F0F0F0"
    number_font_point_size: int = 11
    percent_min_width: int = 34
    border_radius: int = 6
    border_color: str = "#282c34"
    border_width: int = 1
    shadow_margin: int = 4
    shadow_blur_radius: int = 4
    shadow_offset_y: int = 0
    shadow_color: str = "#282c34"
    show_offset_y: int = 18
    hide_offset_y: int = 22
    show_ms: int = 180
    hide_ms: int = 160
    visible_ms: int = 2000


class OverlayVolumeBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0
        self._fill_color = QColor("#8E8E8E")
        self._bg_color = QColor("#727272")

    def setValue(self, value: int) -> None:
        clamped = max(0, min(100, int(value)))
        if clamped == self._value:
            return
        self._value = clamped
        self.update()

    def setColors(self, *, fill_color: str, bg_color: str) -> None:
        fill = QColor(str(fill_color or "#8E8E8E"))
        bg = QColor(str(bg_color or "#727272"))
        self._fill_color = fill if fill.isValid() else QColor("#8E8E8E")
        self._bg_color = bg if bg.isValid() else QColor("#727272")
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)

        draw_rect = rect.adjusted(0, 0, -1, -1)
        radius = draw_rect.height() / 2.0
        painter.setBrush(self._bg_color)
        painter.drawRoundedRect(draw_rect, radius, radius)

        if self._value <= 0:
            return

        raw_fill_width = (draw_rect.width() * self._value) / 100.0
        fill_width = min(draw_rect.width(), max(draw_rect.height(), raw_fill_width))
        fill_rect = draw_rect.adjusted(0, 0, -(draw_rect.width() - int(round(fill_width))), 0)
        fill_radius = min(radius, fill_rect.height() / 2.0, fill_rect.width() / 2.0)
        painter.setBrush(self._fill_color)
        painter.drawRoundedRect(fill_rect, fill_radius, fill_radius)


class VolumeOverlayToast(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setObjectName("OverlayWindow")

        self._style = OverlayStyle()

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._start_hide_animation)
        self._show_animation: QParallelAnimationGroup | None = None
        self._hide_animation: QParallelAnimationGroup | None = None

        inner = QFrame(self)
        inner.setObjectName("Card")
        inner_layout = QHBoxLayout(inner)
        inner_layout.setSpacing(4)
        inner_layout.setAlignment(Qt.AlignCenter)

        self.icon_label = QLabel("")
        self.icon_label.setAlignment(Qt.AlignCenter)
        inner_layout.addWidget(self.icon_label, 0, Qt.AlignCenter)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(2)
        content.setAlignment(Qt.AlignCenter)
        self.title_label = QLabel("Volume")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title_row = QHBoxLayout()
        self.title_row.addWidget(self.title_label, 0, Qt.AlignLeft | Qt.AlignVCenter)
        self.title_row.addStretch(1)
        content.addLayout(self.title_row)

        self.bar = OverlayVolumeBar()
        self.bar_row = QHBoxLayout()
        self.bar_row.addWidget(self.bar, 0, Qt.AlignLeft | Qt.AlignVCenter)
        self.bar_row.addStretch(1)
        content.addLayout(self.bar_row)

        inner_layout.addLayout(content, 1)

        self.percent_label = QLabel("0")
        self.percent_label.setObjectName("Percent")
        self.percent_label.setAlignment(Qt.AlignCenter)
        inner_layout.addWidget(self.percent_label, 0, Qt.AlignCenter)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(inner)
        root.setAlignment(Qt.AlignCenter)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(self._style.shadow_blur_radius)
        shadow.setOffset(0, self._style.shadow_offset_y)
        shadow.setColor(Qt.black)
        inner.setGraphicsEffect(shadow)

        self._inner = inner
        self._inner_layout = inner_layout
        self._root_layout = root
        self._shadow = shadow
        self._bar_row = self.bar_row
        self._title_row = self.title_row
        self._apply_style()

    def show_result(self, result: VolumeMixerResult) -> None:
        title = str(result.title or result.label or "Volume").strip() or "Volume"
        percent = max(0, min(100, int(result.volume_percent)))
        self.title_label.setText(title)
        self.percent_label.setText(str(percent))
        self.bar.setValue(percent)
        self._set_icon(result.icon_path, title)
        target = self._target_position()
        self._timer.stop()
        self._stop_animation(self._hide_animation)
        if not self.isVisible():
            self._play_show_animation(target)
        else:
            self._stop_animation(self._show_animation)
            self.move(target)
            self.setWindowOpacity(1.0)
            self.show()
            self.raise_()
            self._apply_backdrop_effect()
        self._timer.start(self._style.visible_ms)

    def _apply_style(self) -> None:
        style = self._style
        radius = max(2, style.bar_height // 2)
        border_radius = max(0, style.border_radius)
        uses_backdrop = _uses_backdrop(style.backdrop_mode)
        shadow_margin = 0 if uses_backdrop else style.shadow_margin
        shadow_bottom = 0 if uses_backdrop else max(0, style.shadow_offset_y)
        outer_width = style.width + (shadow_margin * 2)
        outer_height = style.height + (shadow_margin * 2) + shadow_bottom

        self._inner.setFixedSize(style.width, style.height)
        self.setFixedSize(outer_width, outer_height)
        self._root_layout.setContentsMargins(
            shadow_margin,
            shadow_margin,
            shadow_margin,
            shadow_margin + shadow_bottom,
        )
        self._inner_layout.setContentsMargins(style.icon_left_padding, 4, 4, 4)

        self.icon_label.setFixedSize(style.icon_size, style.icon_size)
        self.bar.setFixedHeight(style.bar_height)
        self.bar.setFixedWidth(style.bar_width)
        self.bar.setColors(fill_color=style.bar_fill_color, bg_color=style.bar_bg_color)
        self._bar_row.setContentsMargins(style.bar_left_offset, max(0, style.bar_y_offset), 0, max(0, -style.bar_y_offset))
        self.title_row.setContentsMargins(
            style.title_left_padding,
            max(0, style.title_y_offset),
            0,
            max(0, -style.title_y_offset),
        )

        self.title_label.setStyleSheet(
            f"color: {style.title_color};"
        )

        number_font = QFont(self.percent_label.font())
        number_font.setPointSize(style.number_font_point_size)
        number_font.setBold(False)
        self.percent_label.setFont(number_font)
        self._shadow.setEnabled(not uses_backdrop)
        self._shadow.setBlurRadius(style.shadow_blur_radius)
        self._shadow.setOffset(0, style.shadow_offset_y)
        shadow_color = QColor(style.shadow_color)
        self._shadow.setColor(shadow_color)

        card_bg = _qt_rgba(style.bg_color, style.bg_opacity)

        self.setStyleSheet(
            f"""
            QFrame#OverlayWindow {{
                background: transparent;
                border: none;
            }}
            QFrame#Card {{
                background: {card_bg};
                border: {style.border_width}px solid {style.border_color};
                border-radius: {border_radius}px;
            }}
            QLabel {{
                background: transparent;
                color: {style.title_color};
            }}
            QLabel#Percent {{
                color: {style.number_color};
                min-width: {style.percent_min_width}px;
            }}
            """
        )
        self._apply_window_mask(border_radius=border_radius, uses_backdrop=uses_backdrop)
        self._apply_backdrop_effect()

    def _set_icon(self, icon_path: str, title: str) -> None:
        size = self._style.icon_size
        path = ""
        if icon_path:
            with suppress(Exception):
                path = str(Path(icon_path).expanduser())
        if path:
            image = extract_file_icon(path, size=size)
            if image is not None:
                self.icon_label.setStyleSheet("background: transparent;")
                self.icon_label.setPixmap(QPixmap.fromImage(ImageQt(image)))
                self.icon_label.setText("")
                return
            icon = QIcon(path)
            if not icon.isNull():
                self.icon_label.setStyleSheet("background: transparent;")
                self.icon_label.setPixmap(icon.pixmap(size, size))
                self.icon_label.setText("")
                return
        self.icon_label.setStyleSheet("background: transparent;")
        self.icon_label.setPixmap(render_app_icon_pixmap(size=size))
        self.icon_label.setText("")

    def _target_position(self) -> QPoint:
        screen = self.screen()
        if screen is None:
            return self.pos()
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + geo.height() - self.height() - 40
        return QPoint(max(geo.x(), x), max(geo.y(), y))

    def _play_show_animation(self, target: QPoint) -> None:
        start = QPoint(target.x(), target.y() + self._style.show_offset_y)
        self.move(start)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._apply_backdrop_effect()

        pos_anim = QPropertyAnimation(self, b"pos", self)
        pos_anim.setDuration(self._style.show_ms)
        pos_anim.setStartValue(start)
        pos_anim.setEndValue(target)
        pos_anim.setEasingCurve(QEasingCurve.OutCubic)

        opacity_anim = QPropertyAnimation(self, b"windowOpacity", self)
        opacity_anim.setDuration(self._style.show_ms)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(QEasingCurve.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(pos_anim)
        group.addAnimation(opacity_anim)
        self._show_animation = group
        group.start()

    def _start_hide_animation(self) -> None:
        if not self.isVisible():
            return
        self._stop_animation(self._show_animation)
        self._stop_animation(self._hide_animation)

        start = self.pos()
        end = QPoint(start.x(), start.y() + self._style.hide_offset_y)

        pos_anim = QPropertyAnimation(self, b"pos", self)
        pos_anim.setDuration(self._style.hide_ms)
        pos_anim.setStartValue(start)
        pos_anim.setEndValue(end)
        pos_anim.setEasingCurve(QEasingCurve.InCubic)

        opacity_anim = QPropertyAnimation(self, b"windowOpacity", self)
        opacity_anim.setDuration(self._style.hide_ms)
        opacity_anim.setStartValue(max(0.0, float(self.windowOpacity())))
        opacity_anim.setEndValue(0.0)
        opacity_anim.setEasingCurve(QEasingCurve.InCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(pos_anim)
        group.addAnimation(opacity_anim)
        group.finished.connect(self._finish_hide_animation)
        self._hide_animation = group
        group.start()

    def _finish_hide_animation(self) -> None:
        self.hide()
        self.setWindowOpacity(1.0)

    def _stop_animation(self, animation: QParallelAnimationGroup | None) -> None:
        if animation is None:
            return
        if animation.state():
            animation.stop()

    def _apply_backdrop_effect(self) -> None:
        hwnd = int(self.winId()) if self.winId() else 0
        apply_backdrop(
            hwnd,
            mode=self._style.backdrop_mode,
            color=self._style.bg_color,
            opacity=self._style.backdrop_opacity,
        )

    def _apply_window_mask(self, *, border_radius: int, uses_backdrop: bool) -> None:
        if not uses_backdrop or border_radius <= 0:
            self.clearMask()
            return
        path = QPainterPath()
        path.addRoundedRect(self.rect(), border_radius, border_radius)
        region = QRegion(path.toFillPolygon().toPolygon())
        self.setMask(region)

def _qt_rgba(color: str, opacity: int) -> str:
    qcolor = QColor(str(color or "#000000"))
    if not qcolor.isValid():
        qcolor = QColor("#000000")
    alpha = max(0, min(255, int(opacity)))
    return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {alpha})"


def _uses_backdrop(mode: str) -> bool:
    return str(mode or "none").strip().lower() not in {"none", "off", "disabled"}
