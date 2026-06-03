#!/usr/bin/env python
# main.py - Punto de entrada de la aplicación

import sys
import os
import ctypes

# ── Evitar Múltiples Instancias (Mutex Único de Windows) ───────────────
MUTEX_NAME = "Local\\PracticalPedidosSingleInstanceMutex"
kernel32 = ctypes.windll.kernel32
_app_mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    # Mostrar advertencia y salir
    ctypes.windll.user32.MessageBoxW(
        0,
        "La aplicación PRACTICAL PEDIDOS ya se está ejecutando.",
        "Advertencia",
        0x30 | 0x00000000  # MB_ICONWARNING (0x30) | MB_OK (0x00)
    )
    sys.exit(0)

import subprocess
from pathlib import Path

def configurar_playwright():
    """Configura Playwright para encontrar o instalar los navegadores"""
    
    if getattr(sys, 'frozen', False):
        # Estamos en un ejecutable empaquetado
        base_path = sys._MEIPASS
        
        # 1. Intentar usar los navegadores empaquetados en la carpeta del módulo (.local-browsers)
        # Soportamos tanto _internal (PyInstaller v6) como la raíz de base_path (PyInstaller tradicional)
        embedded_browsers = os.path.join(base_path, '_internal', 'playwright', 'driver', 'package', '.local-browsers')
        if not os.path.exists(embedded_browsers):
            embedded_browsers = os.path.join(base_path, 'playwright', 'driver', 'package', '.local-browsers')
            
        if os.path.exists(embedded_browsers):
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = embedded_browsers
            return
            
        # 2. Fallback si existen en ms-playwright de _MEIPASS
        playwright_browsers = os.path.join(base_path, 'ms-playwright')
        if os.path.exists(playwright_browsers):
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = playwright_browsers
            return
        
        # 3. Fallback en APPDATA local del usuario
        app_data = os.path.join(os.environ.get('APPDATA', '.'), 'PracticalPedidos')
        browsers_dir = os.path.join(app_data, 'ms-playwright')
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browsers_dir
        
        # Verificar si ya están instalados
        chromium_path = os.path.join(browsers_dir, 'chromium-*', 'chrome.exe')
        import glob
        if not glob.glob(chromium_path):
            # Instalar navegadores de forma programática si todo lo demás falla
            try:
                print("Instalando navegadores de Playwright...")
                import playwright.__main__
                original_argv = sys.argv
                sys.argv = ['playwright', 'install', 'chromium']
                try:
                    playwright.__main__.main()
                    print("Navegadores instalados correctamente")
                finally:
                    sys.argv = original_argv
            except Exception as e:
                print(f"Error instalando navegadores: {e}")
    else:
        # En desarrollo, usar la instalación normal
        pass

# Configurar Playwright ANTES de importar otros módulos
configurar_playwright()

# Asegurar que el directorio actual está en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from presentation.app import App

if __name__ == "__main__":
    app = App()
    app.mainloop()