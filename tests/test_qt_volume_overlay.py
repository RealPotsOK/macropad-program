from __future__ import annotations

from macropad.core.volume_mixer import VolumeMixerResult
from macropad.qt.services.volume_overlay import VolumeOverlayToast


def test_volume_overlay_show_result_handles_icon_path_without_crashing(qtbot, monkeypatch) -> None:
    monkeypatch.setattr("macropad.qt.services.volume_overlay.apply_backdrop", lambda *args, **kwargs: False)

    overlay = VolumeOverlayToast()
    qtbot.addWidget(overlay)

    overlay.show_result(
        VolumeMixerResult(
            label="spotify.exe",
            title="Spotify",
            matched_sessions=1,
            volume_percent=42,
            icon_path=r"C:\Windows\System32\notepad.exe",
        )
    )

    assert overlay.percent_label.text() == "42"
