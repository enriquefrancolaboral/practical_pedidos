# utils/helpers.py
import tempfile
import os
import atexit
from datetime import datetime

def crear_archivo_temporal(log_fn, prefijo="InformeLibroVenta"):
    """Crea un archivo temporal y registra su limpieza."""
    temp_dir = tempfile.gettempdir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_path = os.path.join(temp_dir, f"{prefijo}_{timestamp}.xlsx")
    
    archivos_temp = [temp_path]
    
    def limpiar():
        for archivo in archivos_temp:
            try:
                if os.path.exists(archivo):
                    os.remove(archivo)
                    log_fn(f"[INFO] Archivo temporal eliminado: {archivo}")
            except Exception as e:
                log_fn(f"[WARN] No se pudo eliminar {archivo}: {e}")
    
    atexit.register(limpiar)
    return temp_path, archivos_temp

def js_escape(valor: str) -> str:
    """Escapa caracteres para inyección segura en JavaScript."""
    return str(valor).replace("\\", "\\\\").replace("'", "\\'")