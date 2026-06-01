# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

# Buscar la carpeta de navegadores de Playwright
playwright_browsers = os.path.expanduser('~\\AppData\\Local\\ms-playwright')

# Crear una lista de datos para incluir
browser_data = []
if os.path.exists(playwright_browsers):
    for item in os.listdir(playwright_browsers):
        src = os.path.join(playwright_browsers, item)
        dst = os.path.join('ms-playwright', item)
        if os.path.isdir(src):
            browser_data.append((src, dst))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('presentation/assets/icono.ico', 'presentation/assets'),
        ('presentation/assets', 'presentation/assets'),
    ] + browser_data,  # Agregar los navegadores
    hiddenimports=[
        'customtkinter',
        'pandas',
        'openpyxl',
        'playwright',
        'playwright.async_api',
        'playwright.sync_api',
        'keyring',
        'keyring.backends.Windows',
        'numpy',
        'sounddevice',
        'edge_tts',
        'miniaudio',
        'asyncio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PracticalPedidos',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Cambia a True para ver errores
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='presentation/assets/icono.ico',
)

# Agregar COLLECT para incluir la carpeta de navegadores
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PracticalPedidos',
)