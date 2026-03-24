from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QObject, Signal

from macropad.qt.pages.stats_page import StatsPage


class _FakeController(QObject):
    keyStateChanged = Signal(int, int, bool)
    encoderChanged = Signal(str)
    lastPacketChanged = Signal(str)
    setupChanged = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.store = SimpleNamespace(keys=[(0, 0), (0, 1), (1, 0), (1, 1)])


def test_stats_page_tracks_key_and_encoder_counts(qtbot) -> None:
    controller = _FakeController()
    page = StatsPage(controller)
    qtbot.addWidget(page)
    page.show()

    controller.keyStateChanged.emit(0, 0, True)
    controller.keyStateChanged.emit(0, 0, False)
    controller.keyStateChanged.emit(1, 1, True)
    controller.encoderChanged.emit("ENC=+2")
    controller.encoderChanged.emit("ENC=-1")
    controller.encoderChanged.emit("ENC_SW=1")
    controller.lastPacketChanged.emit("12:34:56")
    page.refresh()

    assert "Total key presses: 2" in page.total_keys_label.text()
    assert "up 2" in page.encoder_summary_label.text().lower()
    assert "down 1" in page.encoder_summary_label.text().lower()
    assert "switch 1" in page.encoder_summary_label.text().lower()
    assert "12:34:56" in page.last_packet_label.text()

