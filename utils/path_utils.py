# utils/path_utils.py
import sys
import os

def resource_path(filename):
    """Obtiene la ruta correcta del archivo (funciona en desarrollo y ejecutable)"""
    if getattr(sys, 'frozen', False):
        # Si está compilado como .exe
        base = sys._MEIPASS
    else:
        # En desarrollo: vamos al directorio raíz del proyecto
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, filename)