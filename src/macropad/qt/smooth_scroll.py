from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt
from PySide6.QtWidgets import QAbstractScrollArea


class SmoothWheelScroll(QObject):
    def __init__(self, area: QAbstractScrollArea, *, duration_ms: int = 180, wheel_step: int = 84) -> None:
        super().__init__(area)
        self._area = area
        self._wheel_step = max(1, int(wheel_step))
        self._target_value = area.verticalScrollBar().value()
        self._animation = QPropertyAnimation(area.verticalScrollBar(), b"value", self)
        self._animation.setDuration(max(1, int(duration_ms)))
        self._animation.setEasingCurve(QEasingCurve.OutCubic)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if event.type() != QEvent.Type.Wheel:
            return False

        if not bool(getattr(event, "angleDelta", lambda: 0)().y()) and not bool(
            getattr(event, "pixelDelta", lambda: 0)().y()
        ):
            return False

        modifiers = getattr(event, "modifiers", lambda: Qt.KeyboardModifier.NoModifier)()
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            return False

        bar = self._area.verticalScrollBar()
        minimum = int(bar.minimum())
        maximum = int(bar.maximum())
        current = int(bar.value())
        pixel_delta = int(getattr(event, "pixelDelta", lambda: 0)().y())
        angle_delta = int(getattr(event, "angleDelta", lambda: 0)().y())

        if pixel_delta:
            step_delta = pixel_delta
        else:
            steps = angle_delta / 120.0
            step_delta = int(round(steps * self._wheel_step))

        if step_delta == 0:
            return False

        self._target_value = max(minimum, min(maximum, self._target_value - step_delta))

        self._animation.stop()
        self._animation.setStartValue(current)
        self._animation.setEndValue(self._target_value)
        self._animation.start()

        event.accept()
        return True


def install_smooth_wheel_scroll(
    area: QAbstractScrollArea,
    *,
    duration_ms: int = 180,
    wheel_step: int = 84,
) -> SmoothWheelScroll:
    helper = SmoothWheelScroll(area, duration_ms=duration_ms, wheel_step=wheel_step)
    area.viewport().installEventFilter(helper)
    area.installEventFilter(helper)

    # Keep python reference alive for the same lifetime as the widget.
    helpers = list(getattr(area, "_smooth_wheel_helpers", []))
    helpers.append(helper)
    setattr(area, "_smooth_wheel_helpers", helpers)
    return helper

