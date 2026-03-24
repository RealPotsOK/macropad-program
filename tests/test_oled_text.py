from __future__ import annotations

import asyncio

import macropad.core.oled_text as oled_text
from macropad.core.profile import Profile


def test_description_template_for_label_preserves_custom_text() -> None:
    assert (
        oled_text.description_template_for_label(
            oled_text.DESCRIPTION_PRESET_CUSTOM,
            current_value="Volume 75",
        )
        == "Volume 75"
    )


def test_infer_description_preset_label_matches_known_template() -> None:
    assert oled_text.infer_description_preset_label("{spotify_track}|{spotify_artist}") == "Spotify now playing"
    assert oled_text.infer_description_preset_label("hello") == oled_text.DESCRIPTION_PRESET_CUSTOM


def test_description_refresh_interval_uses_fastest_dynamic_token() -> None:
    assert oled_text.description_refresh_interval("{datetime}") == 15.0
    assert oled_text.description_refresh_interval("{time} {spotify_track}") == 2.0
    assert oled_text.description_refresh_interval("plain text") is None


def test_render_template_text_replaces_missing_tokens_with_blank() -> None:
    assert oled_text.render_template_text("Now {missing}", {}) == "Now"


def test_render_profile_display_lines_supports_dynamic_tokens(monkeypatch) -> None:
    async def fake_media() -> dict[str, str]:
        return {
            "spotify_track": "Song",
            "spotify_artist": "Artist",
            "spotify_track_artist": "Song - Artist",
            "media_track": "",
            "media_artist": "",
            "media_track_artist": "",
        }

    monkeypatch.setattr(oled_text, "_read_media_context", fake_media)

    profile = Profile(name="Profile {profile_slot}", description="{spotify_track}|{spotify_artist}")
    lines = asyncio.run(oled_text.render_profile_display_lines(profile, slot=4, port="COM7"))

    assert lines == ("Profile 4", "Song", "Artist")


def test_render_profile_display_lines_keeps_profile_name_for_single_line_description(monkeypatch) -> None:
    async def fake_media() -> dict[str, str]:
        return {
            "spotify_track": "",
            "spotify_artist": "",
            "spotify_track_artist": "",
            "media_track": "",
            "media_artist": "",
            "media_track_artist": "",
        }

    monkeypatch.setattr(oled_text, "_read_media_context", fake_media)

    profile = Profile(name="Profile {profile_slot}", description="COM {port}")
    lines = asyncio.run(oled_text.render_profile_display_lines(profile, slot=2, port="COM7"))

    assert lines == ("Profile 2", "COM COM7")


def test_render_profile_display_lines_preserves_full_lines_for_device_layout(monkeypatch) -> None:
    async def fake_media() -> dict[str, str]:
        return {
            "spotify_track": "AAAAAAAAAAAAAAAAAAAAAAAAA",
            "spotify_artist": "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
            "spotify_track_artist": "",
            "media_track": "",
            "media_artist": "",
            "media_track_artist": "",
        }

    monkeypatch.setattr(oled_text, "_read_media_context", fake_media)

    profile = Profile(name="Profile 4", description="{spotify_track}|{spotify_artist}")
    lines = asyncio.run(oled_text.render_profile_display_lines(profile, slot=4, port="COM7"))

    assert lines == (
        "Profile 4",
        "AAAAAAAAAAAAAAAAAAAAAAAAA",
        "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
    )
