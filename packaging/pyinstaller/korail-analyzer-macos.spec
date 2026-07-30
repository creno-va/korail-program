# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parents[1]
APP_VERSION = os.environ.get("KORAIL_APP_VERSION", "0.0.0")

datas = [
    (str(ROOT / "README.md"), "."),
    (str(ROOT / "src" / "korail_program" / "assets" / "fonts"), "korail_program/assets/fonts"),
]
datas += collect_data_files("qtawesome")

hiddenimports = collect_submodules("qtawesome") + collect_submodules("korail_program")

a = Analysis(
    [str(ROOT / "src" / "korail_program" / "app" / "main.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=[],
    datas=datas,
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
    name="KorailAnalyzer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=os.environ.get("KORAIL_TARGET_ARCH") or None,
    codesign_identity=os.environ.get("KORAIL_CODESIGN_IDENTITY") or None,
    entitlements_file=os.environ.get("KORAIL_ENTITLEMENTS_FILE") or None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="KorailAnalyzer",
)

app = BUNDLE(
    coll,
    name="Korail Analyzer.app",
    icon=None,
    bundle_identifier="kr.co.korail.analyzer",
    info_plist={
        "CFBundleName": "Korail Analyzer",
        "CFBundleDisplayName": "Korail 지장수목 분석",
        "CFBundleShortVersionString": APP_VERSION,
        "CFBundleVersion": APP_VERSION,
        "LSApplicationCategoryType": "public.app-category.utilities",
        "LSMinimumSystemVersion": "14.0",
        "NSHighResolutionCapable": True,
    },
)
