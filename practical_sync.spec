# practical_sync.spec
from PyInstaller.utils.hooks import collect_data_files, collect_all

# ── Rutas de Chromium ─────────────────────────────────────────────────────────
CHROMIUM_DIR        = r"C:\Users\PRACTICAL\AppData\Local\ms-playwright\chromium-1217"
CHROMIUM_DEST       = "ms-playwright/chromium-1217"

CHROMIUM_HS_DIR     = r"C:\Users\PRACTICAL\AppData\Local\ms-playwright\chromium_headless_shell-1217"
CHROMIUM_HS_DEST    = "ms-playwright/chromium_headless_shell-1217"

# ── Recolectar binarios/datos de keyring ──────────────────────────────────────
keyring_datas, keyring_binaries, keyring_hiddenimports = collect_all('keyring')

# ─────────────────────────────────────────────────────────────────────────────

a = Analysis(
    ['gui.py'],
    pathex=['.'],
    binaries=[
        *keyring_binaries,
    ],
    datas=[
        # Módulos del proyecto
        ('modules',  'modules'),
        ('utils',    'utils'),
        # Recursos
        ('icono.ico', '.'),
        # Chromium normal (headless=False)
        (CHROMIUM_DIR,    CHROMIUM_DEST),
        # Chromium headless shell (headless=True)
        (CHROMIUM_HS_DIR, CHROMIUM_HS_DEST),
        # Datos internos de Playwright, CustomTkinter y keyring
        *collect_data_files('playwright'),
        *collect_data_files('customtkinter'),
        *keyring_datas,
    ],
    hiddenimports=[
        'playwright',
        'playwright.sync_api',
        'customtkinter',
        'pandas',
        'openpyxl',
        'dotenv',
        'requests',
        # keyring y sus backends de Windows
        'keyring',
        'keyring.backends',
        'keyring.backends.Windows',
        'keyring.backends.fail',
        'keyring.backends.null',
        *keyring_hiddenimports,
    ],
    hookspath=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PracticalSync',
    icon='icono.ico',
    console=False,      # Cambiar a True temporalmente si necesitás ver errores
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='PracticalSync',
)
