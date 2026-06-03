# practical_pedidos.spec
# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path
import customtkinter

customtkinter_path = os.path.dirname(customtkinter.__file__)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('presentation/assets', 'presentation/assets'),
        (os.path.join(customtkinter_path, 'assets'), 'customtkinter/assets'),
    ],
    hiddenimports=[
        'customtkinter',
        'openpyxl',
        'playwright',
        'playwright.sync_api',
        'playwright.async_api',
        'edge_tts',
        'keyring',
        'keyring.backends.Windows',
        'asyncio',
        'threading',
        'queue',
        'tempfile',
        'glob',
        'subprocess',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['numpy', 'pandas', 'sounddevice', 'miniaudio', 'cffi', '_cffi_backend'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PracticalPedidos',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Sin ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='presentation/assets/icono.ico' if os.path.exists('presentation/assets/icono.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PracticalPedidos',
)