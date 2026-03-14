from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path
import sys

from PIL import Image

BI_RGB = 0
DIB_RGB_COLORS = 0
DI_NORMAL = 0x0003


class RGBQUAD(ctypes.Structure):
    _fields_ = [
        ("rgbBlue", wintypes.BYTE),
        ("rgbGreen", wintypes.BYTE),
        ("rgbRed", wintypes.BYTE),
        ("rgbReserved", wintypes.BYTE),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", RGBQUAD * 1),
    ]


def extract_file_icon(path: str | Path, *, size: int = 32) -> Image.Image | None:
    if sys.platform != "win32":
        return None

    icon_path = Path(path).expanduser()
    if not icon_path.exists():
        return None

    shell32 = ctypes.windll.shell32
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    large = wintypes.HICON()
    small = wintypes.HICON()
    extracted = shell32.ExtractIconExW(str(icon_path), 0, ctypes.byref(large), ctypes.byref(small), 1)
    if extracted <= 0:
        return None

    hicon = small.value or large.value
    if not hicon:
        if large.value:
            user32.DestroyIcon(large)
        if small.value:
            user32.DestroyIcon(small)
        return None

    hdc = user32.GetDC(None)
    memdc = gdi32.CreateCompatibleDC(hdc)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = int(size)
    bmi.bmiHeader.biHeight = -int(size)
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB

    bits = ctypes.c_void_p()
    hbitmap = gdi32.CreateDIBSection(memdc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
    if not hbitmap:
        _cleanup_icon_handles(user32, large, small, hicon)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(None, hdc)
        return None

    old_bitmap = gdi32.SelectObject(memdc, hbitmap)
    try:
        if bits.value:
            ctypes.memset(bits.value, 0, size * size * 4)
        user32.DrawIconEx(memdc, 0, 0, hicon, size, size, 0, None, DI_NORMAL)
        if not bits.value:
            return None
        raw = ctypes.string_at(bits.value, size * size * 4)
        image = Image.frombuffer("RGBA", (size, size), raw, "raw", "BGRA", 0, 1).copy()
        return image
    finally:
        gdi32.SelectObject(memdc, old_bitmap)
        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(None, hdc)
        _cleanup_icon_handles(user32, large, small, hicon)


def _cleanup_icon_handles(user32, large: wintypes.HICON, small: wintypes.HICON, used_icon: int) -> None:
    for handle in (small.value, large.value):
        if handle:
            user32.DestroyIcon(handle)
