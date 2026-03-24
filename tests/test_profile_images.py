from __future__ import annotations

from pathlib import Path

import pytest

from macropad.core.profile_images import (
    ensure_image_dir,
    find_profile_image_path,
    load_profile_image_payload,
    pack_palette_indices_2bpp,
)


def test_ensure_image_dir_creates_folder(tmp_path: Path) -> None:
    image_dir = tmp_path / "img"
    assert not image_dir.exists()
    created = ensure_image_dir(image_dir)
    assert created.exists()
    assert created.is_dir()


def test_find_profile_image_path_prefers_known_extensions(tmp_path: Path) -> None:
    image_dir = ensure_image_dir(tmp_path / "img")
    png = image_dir / "prf_2.png"
    jpg = image_dir / "prf_2.jpg"
    jpg.write_bytes(b"x")
    png.write_bytes(b"y")

    found = find_profile_image_path(image_dir, 2)
    assert found == png


def test_load_profile_image_payload_from_raw_binary(tmp_path: Path) -> None:
    path = tmp_path / "prf_1.bin"
    payload = bytes([0xAA]) * 2048
    path.write_bytes(payload)
    loaded = load_profile_image_payload(path)
    assert loaded == payload


def test_load_profile_image_payload_from_raw_binary_rejects_wrong_size(tmp_path: Path) -> None:
    path = tmp_path / "prf_1.raw"
    path.write_bytes(bytes([0xAA]) * 128)
    with pytest.raises(ValueError):
        _ = load_profile_image_payload(path)


def test_pack_palette_indices_2bpp_order() -> None:
    packed = pack_palette_indices_2bpp([0, 1, 2, 3])
    assert packed == bytes([0x1B])


def test_pack_palette_indices_2bpp_requires_multiples_of_four() -> None:
    with pytest.raises(ValueError):
        _ = pack_palette_indices_2bpp([0, 1, 2])
