# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

repo_root = Path(os.getcwd()).resolve()
src_root = repo_root / "src"
launcher = repo_root / "scripts" / "windows_gui_launcher.py"
app_icon = repo_root / "assets" / "MP_Icon.ico"

pyside_datas, pyside_binaries, pyside_hiddenimports = collect_all("PySide6")
extra_datas = [
    (str(repo_root / "assets" / "MP_Icon.png"), "assets"),
    (str(repo_root / "assets" / "MP_Icon.ico"), "assets"),
]
hiddenimports = []
hiddenimports += pyside_hiddenimports
hiddenimports += collect_submodules("qasync")
hiddenimports += collect_submodules("shiboken6")
hiddenimports += collect_submodules("comtypes")
hiddenimports += collect_submodules("pycaw")
hiddenimports += collect_submodules("winsdk")

a = Analysis(
    [str(launcher)],
    pathex=[str(src_root)],
    binaries=pyside_binaries,
    datas=pyside_datas + extra_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MacroPad Controller",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(app_icon),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MacroPad Controller",
)
