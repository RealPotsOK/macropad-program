from __future__ import annotations

from types import SimpleNamespace

import macropad_ble.gui_app as gui_app
from macropad_ble.config import Settings


def test_gui_parser_accepts_hidden_flag() -> None:
    parser = gui_app.build_parser()
    args = parser.parse_args(["--hidden", "--port", "COM13"])

    assert args.hidden is True
    assert args.port == "COM13"


def test_gui_main_signals_existing_instance(monkeypatch) -> None:
    state = {"signaled": False}

    class FakeGuard:
        def acquire(self) -> bool:
            return False

        def signal_restore(self) -> bool:
            state["signaled"] = True
            return True

        def close(self) -> None:
            return None

    monkeypatch.setattr(gui_app, "SingleInstanceGuard", lambda _app_id: FakeGuard())
    monkeypatch.setattr(gui_app, "load_settings", lambda **_kwargs: Settings())
    monkeypatch.setattr(gui_app, "configure_logging", lambda _level: None)

    assert gui_app.main([]) == 0
    assert state["signaled"] is True


def test_gui_main_passes_hidden_launch_to_run_gui(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeGuard:
        def acquire(self) -> bool:
            return True

        def close(self) -> None:
            return None

    async def fake_run_gui(settings: Settings, **kwargs) -> int:
        captured["settings"] = settings
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(gui_app, "SingleInstanceGuard", lambda _app_id: FakeGuard())
    monkeypatch.setattr(gui_app, "load_settings", lambda **_kwargs: Settings(port="COM13"))
    monkeypatch.setattr(gui_app, "configure_logging", lambda _level: None)
    monkeypatch.setattr(gui_app, "run_gui", fake_run_gui)
    monkeypatch.setattr(gui_app.sys, "argv", ["C:\\Apps\\MacroPad Controller.exe"])

    assert gui_app.main(["--hidden"]) == 0
    assert captured["start_hidden"] is True
    assert captured["launch_command"] == ["C:\\Apps\\MacroPad Controller.exe", "--hidden"]
