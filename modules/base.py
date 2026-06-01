# modules/base.py
from abc import ABC, abstractmethod
from utils.network import hay_conexion_internet, esperar_conexion_red

class BaseSincronizador(ABC):
    """Clase base para todos los sincronizadores."""
    
    def __init__(self, page, log_fn, stop_event=None, reset_event=None):
        self.page = page
        self.log = log_fn
        self.stop_event = stop_event
        self.reset_event = reset_event
    
    def verificar_pausa(self):
        """Verifica si se debe pausar la ejecución."""
        if self.reset_event and self.reset_event.is_set():
            raise KeyboardInterrupt("Reinicio forzado")
        
        if self.stop_event and self.stop_event.is_set():
            self.log("\n[PAUSA] Esperando reanudación...")
            while self.stop_event.is_set():
                if self.reset_event and self.reset_event.is_set():
                    raise KeyboardInterrupt("Reinicio forzado")
                if not hay_conexion_internet():
                    esperar_conexion_red(self.log, self.stop_event, self.reset_event)
                self.stop_event.wait(1)
            self.log("[INFO] Reanudado.")
    
    def seleccionar_select2(self, select_id: str, termino: str, timeout: int = 10000) -> bool:
        """Selecciona una opción en un campo Select2."""
        try:
            self.log(f"  → Buscando '{termino}' en Select2 {select_id}...")
            self.page.click(f"#{select_id} span.select2-selection")
            search = self.page.wait_for_selector("input.select2-search__field", state="visible")
            search.focus()
            self.page.fill("input.select2-search__field", termino)
            self.page.wait_for_selector(
                f"ul#select2-{select_id}-results li.select2-results__option:first-child",
                timeout=timeout
            )
            self.page.click(f"ul#select2-{select_id}-results li.select2-results__option:first-child")
            return True
        except Exception as e:
            self.log(f"  [ERROR] Select2 '{select_id}': {e}")
            return False
    
    @abstractmethod
    def sincronizar(self, datos):
        """Método principal de sincronización."""
        pass