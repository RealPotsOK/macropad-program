from __future__ import annotations

from concurrent.futures import Future

import macropad.qt.app as qt_app
from macropad.config import Settings


class _FakeSignal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs) -> None:
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _FakeApp:
    def __init__(self) -> None:
        self.aboutToQuit = _FakeSignal()


class _FakeLoop:
    def __init__(self, app: _FakeApp) -> None:
        self.app = app
        self._scheduled = []

    def create_future(self) -> Future:
        return Future()

    def call_soon(self, callback) -> None:
        self._scheduled.append(callback)

    def run_until_complete(self, future: Future) -> int:
        for callback in list(self._scheduled):
            callback()
        self.app.aboutToQuit.emit()
        return int(future.result())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_run_qt_app_passes_hidden_startup_flag(monkeypatch) -> None:
    captured: dict[str, object] = {}
    fake_app = _FakeApp()

    class FakeWindow:
        def __init__(self, settings: Settings, **kwargs) -> None:
            captured["settings"] = settings
            captured["kwargs"] = kwargs
            self.exitRequested = _FakeSignal()
            self.reconnectRequested = _FakeSignal()

        def startup(self, *, hidden: bool = False) -> None:
            captured["hidden"] = hidden

    monkeypatch.setattr(qt_app, "_make_application", lambda: fake_app)
    monkeypatch.setattr(qt_app, "_apply_theme", lambda _app: None)
    monkeypatch.setattr(qt_app, "MacroPadMainWindow", FakeWindow)
    monkeypatch.setattr(qt_app, "QEventLoop", _FakeLoop)
    monkeypatch.setattr(qt_app.asyncio, "set_event_loop", lambda _loop: None)

    result = qt_app.run_qt_app(Settings(), start_hidden=True)

    assert result == 0
    assert captured["hidden"] is True
