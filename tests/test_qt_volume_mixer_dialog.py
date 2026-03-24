from __future__ import annotations

from macropad.qt.dialogs.volume_mixer_dialog import VolumeMixerDialog
from macropad.core.volume_mixer import VolumeMixerTarget


def test_volume_mixer_dialog_uses_selected_target_value(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(
        "macropad.qt.dialogs.volume_mixer_dialog.list_volume_mixer_targets",
        lambda: [VolumeMixerTarget("process", "spotify.exe", "spotify.exe - Spotify")],
    )

    dialog = VolumeMixerDialog(current_value="", parent=None)
    qtbot.addWidget(dialog)
    dialog.target.setCurrentIndex(1)

    assert dialog.value() == "kind=process;target=spotify.exe;step=0.050"


def test_volume_mixer_dialog_keeps_typed_custom_target(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(
        "macropad.qt.dialogs.volume_mixer_dialog.list_volume_mixer_targets",
        lambda: [],
    )

    dialog = VolumeMixerDialog(current_value="", parent=None)
    qtbot.addWidget(dialog)
    dialog.target.setCurrentText("opera.exe")
    dialog.step.setValue(-0.05)

    assert dialog.value() == "kind=process;target=opera.exe;step=-0.050"
