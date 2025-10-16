# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# Collect Playwright data files and binaries
playwright_datas = collect_data_files('playwright')
playwright_binaries = collect_dynamic_libs('playwright')
fake_useragent_datas = collect_data_files('fake_useragent')
all_datas = playwright_datas + fake_useragent_datas


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=playwright_binaries,
    datas=all_datas,
    hiddenimports=[
        'playwright',
        'playwright.sync_api',
        'playwright.async_api',
        'playwright._impl._driver',
        'playwright._impl._transport',
    ],
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
    a.binaries,
    a.datas,
    [],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX to avoid issues with Playwright
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
