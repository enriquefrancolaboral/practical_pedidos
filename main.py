#!/usr/bin/env python
# main.py - Punto de entrada de la aplicación

import sys
import os
import subprocess
from pathlib import Path

def configurar_playwright():
    """Configura Playwright para encontrar o instalar los navegadores"""
    
    if getattr(sys, 'frozen', False):
        # Estamos en un ejecutable empaquetado
        base_path = sys._MEIPASS
        playwright_browsers = os.path.join(base_path, 'ms-playwright')
        
        # Verificar si existen los navegadores en el empaquetado
        if os.path.exists(playwright_browsers):
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = playwright_browsers
            return
        
        # Si no están empaquetados, instalarlos en el directorio local del usuario
        app_data = os.path.join(os.environ.get('APPDATA', '.'), 'PracticalPedidos')
        browsers_dir = os.path.join(app_data, 'ms-playwright')
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = browsers_dir
        
        # Verificar si ya están instalados
        chromium_path = os.path.join(browsers_dir, 'chromium-*', 'chrome.exe')
        import glob
        if not glob.glob(chromium_path):
            # Instalar navegadores
            try:
                print("Instalando navegadores de Playwright...")
                subprocess.run([
                    sys.executable, '-m', 'playwright', 'install', 'chromium'
                ], check=True, capture_output=True)
                print("Navegadores instalados correctamente")
            except Exception as e:
                print(f"Error instalando navegadores: {e}")
                # Intentar con playwright install directo
                try:
                    subprocess.run(['playwright', 'install', 'chromium'], check=True)
                except:
                    pass
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