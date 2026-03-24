from __future__ import annotations

import macropad.core.volume_mixer as volume_mixer


class _FakeProcess:
    def __init__(self, name: str) -> None:
        self._name = name

    def name(self) -> str:
        return self._name


class _FakeSimpleAudioVolume:
    def __init__(self, level: float) -> None:
        self.level = level

    def GetMasterVolume(self) -> float:
        return self.level

    def SetMasterVolume(self, value: float, _event_context) -> None:
        self.level = value


class _FakeSession:
    def __init__(self, process_name: str, display_name: str, level: float) -> None:
        self.Process = _FakeProcess(process_name)
        self.DisplayName = display_name
        self.SimpleAudioVolume = _FakeSimpleAudioVolume(level)


def test_parse_volume_mixer_defaults() -> None:
    spec = volume_mixer.parse_volume_mixer_value("")
    assert spec.target_kind == "process"
    assert spec.target_value == ""
    assert spec.step == 0.05


def test_parse_volume_mixer_round_trip() -> None:
    original = volume_mixer.VolumeMixerSpec(target_kind="display", target_value="Spotify", step=0.12)
    text = volume_mixer.format_volume_mixer_value(original)
    parsed = volume_mixer.parse_volume_mixer_value(text)
    assert parsed.target_kind == "display"
    assert parsed.target_value == "Spotify"
    assert parsed.step == 0.12


def test_parse_volume_mixer_preserves_negative_step() -> None:
    parsed = volume_mixer.parse_volume_mixer_value("kind=process;target=spotify.exe;step=-0.05")
    assert parsed.step == -0.05


def test_list_volume_mixer_targets_dedupes_process_names(monkeypatch) -> None:
    monkeypatch.setattr(volume_mixer.sys, "platform", "win32")
    targets = volume_mixer.list_volume_mixer_targets(
        session_provider=lambda: [
            _FakeSession("spotify.exe", "Spotify", 0.50),
            _FakeSession("spotify.exe", "Spotify", 0.70),
            _FakeSession("opera.exe", "Opera GX", 0.35),
        ]
    )

    labels = [item.label for item in targets]
    assert any("spotify.exe" in label.lower() for label in labels)
    assert any("opera.exe" in label.lower() for label in labels)
    assert len([item for item in targets if item.target_value.lower() == "spotify.exe"]) == 1


def test_change_volume_mixer_volume_updates_matching_sessions(monkeypatch) -> None:
    monkeypatch.setattr(volume_mixer.sys, "platform", "win32")
    session_a = _FakeSession("spotify.exe", "Spotify", 0.50)
    session_b = _FakeSession("spotify.exe", "Spotify", 0.25)
    session_c = _FakeSession("opera.exe", "Opera GX", 0.90)

    result = volume_mixer.change_volume_mixer_volume(
        "kind=process;target=spotify.exe;step=0.10",
        direction=-1,
        session_provider=lambda: [session_a, session_b, session_c],
    )

    assert result.matched_sessions == 2
    assert result.title == "Spotify"
    assert session_a.SimpleAudioVolume.level == 0.40
    assert session_b.SimpleAudioVolume.level == 0.15
    assert session_c.SimpleAudioVolume.level == 0.90
    assert result.volume_percent == 15


def test_change_volume_mixer_volume_requires_active_target(monkeypatch) -> None:
    monkeypatch.setattr(volume_mixer.sys, "platform", "win32")
    try:
        volume_mixer.change_volume_mixer_volume(
            "kind=process;target=spotify.exe;step=0.05",
            session_provider=lambda: [],
        )
    except volume_mixer.VolumeMixerError as exc:
        assert "No active audio sessions matched" in str(exc)
    else:
        raise AssertionError("Expected a VolumeMixerError for missing sessions.")


def test_negative_step_inverts_encoder_direction(monkeypatch) -> None:
    monkeypatch.setattr(volume_mixer.sys, "platform", "win32")
    session = _FakeSession("spotify.exe", "Spotify", 0.50)

    result = volume_mixer.change_volume_mixer_volume(
        "kind=process;target=spotify.exe;step=-0.05",
        direction=1,
        session_provider=lambda: [session],
    )

    assert session.SimpleAudioVolume.level == 0.45
    assert result.volume_percent == 45
