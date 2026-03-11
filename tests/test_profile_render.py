from __future__ import annotations

from macropad_ble.ui.profile import Profile, create_default_profile, profile_from_dict, profile_to_dict, render_profile_oled_lines


def test_profile_oled_round_trip() -> None:
    profile = create_default_profile("Gaming", keys=[(0, 0)])
    profile.oled_line1 = "Profile {profile_slot}"
    profile.oled_line2 = "{profile_name}"
    raw = profile_to_dict(profile)
    loaded = profile_from_dict(raw, fallback_name="Fallback", keys=[(0, 0)])
    assert loaded.oled_line1 == "Profile {profile_slot}"
    assert loaded.oled_line2 == "{profile_name}"


def test_render_profile_oled_lines_substitutes_tokens() -> None:
    profile = Profile(name="Editing")
    profile.oled_line1 = "Slot {profile_slot}"
    profile.oled_line2 = "Name {profile_name}"
    line1, line2 = render_profile_oled_lines(profile, slot=3)
    assert line1 == "Slot 3"
    assert line2 == "Name Editing"


def test_render_profile_oled_lines_handles_bad_template() -> None:
    profile = Profile(name="Default")
    profile.oled_line1 = "{broken"
    profile.oled_line2 = "ok"
    line1, line2 = render_profile_oled_lines(profile, slot=1)
    assert line1 == "{broken"
    assert line2 == "ok"


def test_profile_description_round_trip() -> None:
    profile = create_default_profile("Profile 1", keys=[(0, 0)])
    profile.description = "Volume 75"
    raw = profile_to_dict(profile)
    loaded = profile_from_dict(raw, fallback_name="Fallback", keys=[(0, 0)])
    assert loaded.name == "Profile 1"
    assert loaded.description == "Volume 75"
