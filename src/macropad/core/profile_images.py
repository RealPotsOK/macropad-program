from __future__ import annotations

from pathlib import Path
from typing import Iterable

PROFILE_IMAGE_PREFIX = "prf_"
PROFILE_IMAGE_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".bin",
    ".raw",
)
OLED_PALETTE_RGB: tuple[tuple[int, int, int], ...] = (
    (0, 0, 0),       # black
    (0, 0, 255),     # blue
    (255, 255, 0),   # yellow
    (255, 0, 0),     # red
)


def ensure_image_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def find_profile_image_path(image_dir: Path, slot: int) -> Path | None:
    stem = f"{PROFILE_IMAGE_PREFIX}{int(slot)}"
    for ext in PROFILE_IMAGE_EXTENSIONS:
        candidate = image_dir / f"{stem}{ext}"
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def load_profile_image_payload(path: Path, *, width: int = 128, height: int = 64) -> bytes:
    expected_bytes = (width * height) // 4
    suffix = path.suffix.strip().lower()
    if suffix in {".bin", ".raw"}:
        payload = path.read_bytes()
        if len(payload) != expected_bytes:
            raise ValueError(f"Raw payload in {path} must be exactly {expected_bytes} bytes.")
        return payload

    try:
        from PIL import Image  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "Image conversion requires Pillow. Install it with: pip install pillow"
        ) from exc

    with Image.open(path) as source:
        rgb = source.convert("RGB")
        if hasattr(Image, "Resampling"):
            resized = rgb.resize((width, height), Image.Resampling.LANCZOS)
        else:  # pragma: no cover - compatibility for older Pillow
            resized = rgb.resize((width, height), Image.LANCZOS)
        return _pack_image_to_2bpp(resized, width=width, height=height)


def _pack_image_to_2bpp(image: object, *, width: int, height: int) -> bytes:
    # PIL Image API is duck-typed here so tests do not need Pillow at import time.
    pixel = image.load()  # type: ignore[attr-defined]
    palette_indices = bytearray(width * height)
    out_index = 0
    for y in range(height):
        for x in range(width):
            rgb = pixel[x, y]
            if isinstance(rgb, int):
                rgb_triplet = (rgb, rgb, rgb)
            else:
                rgb_triplet = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
            palette_indices[out_index] = _nearest_palette_index(rgb_triplet)
            out_index += 1
    return pack_palette_indices_2bpp(palette_indices)


def pack_palette_indices_2bpp(palette_indices: Iterable[int]) -> bytes:
    indices = [int(value) & 0x03 for value in palette_indices]
    if len(indices) % 4 != 0:
        raise ValueError("2bpp packing requires palette index count divisible by 4.")

    payload = bytearray(len(indices) // 4)
    out = 0
    for offset in range(0, len(indices), 4):
        a = indices[offset]
        b = indices[offset + 1]
        c = indices[offset + 2]
        d = indices[offset + 3]
        payload[out] = (a << 6) | (b << 4) | (c << 2) | d
        out += 1
    return bytes(payload)


def _nearest_palette_index(rgb: tuple[int, int, int]) -> int:
    best_index = 0
    best_distance = None
    red, green, blue = rgb
    for index, palette_rgb in enumerate(OLED_PALETTE_RGB):
        dr = red - palette_rgb[0]
        dg = green - palette_rgb[1]
        db = blue - palette_rgb[2]
        distance = (dr * dr) + (dg * dg) + (db * db)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_index = index
    return best_index
