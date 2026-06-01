# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('presentation/assets', 'presentation/assets'), ('C:\\Users\\PRACTICAL\\AppData\\Local\\ms-playwright\\chromium-1217', 'ms-playwright\\chromium-1217'), ('C:\\Users\\PRACTICAL\\AppData\\Local\\ms-playwright\\chromium_headless_shell-1217', 'ms-playwright\\chromium_headless_shell-1217')],
    hiddenimports=['customtkinter', 'pandas', 'openpyxl', 'playwright', 'playwright.sync_api', 'playwright.async_api', 'keyring', 'keyring.backends.Windows'],
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
    name='PracticalPedidos',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['presentation\\assets\\icono.ico'],
)
