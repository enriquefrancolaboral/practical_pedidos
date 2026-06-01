# modules/sync_pedidos.py
from modules.base import BaseSincronizador
from utils.network import navegar_con_red
import os
import sys

NODO_LIBRO_VENTA_URL = "https://nodo-practical.nodosolutions.com/LibroVenta/Index"

class SincronizadorPedidos(BaseSincronizador):
    """
    Módulo especialista de Pedidos que aplica filtros y descarga el reporte de ventas en NODO.
    """

    def _verificar_reset(self):
        """Lanza KeyboardInterrupt si se solicitó reinicio."""
        if self.reset_event and self.reset_event.is_set():
            raise KeyboardInterrupt("Reinicio forzado")

    def sincronizar(self, credenciales_dict):
        self.log(f"\n{'='*50}")
        self.log("INICIANDO DESCARGA DE PEDIDOS DESDE NODO")
        self.log(f"{'='*50}")

        self._verificar_reset()
        self.verificar_pausa()

        self.log("[PEDIDOS] Navegando a la página del Libro de Ventas en NODO.")
        if not navegar_con_red(self.page, NODO_LIBRO_VENTA_URL, self.log, self.stop_event, self.reset_event):
            self.log("[ERROR] No se pudo navegar a la página del Libro de Ventas.")
            return

        self._verificar_reset()
        self.verificar_pausa()

        self.log("[PEDIDOS] Aplicando filtros en Libro de Ventas (Concepto: Pedido, Consolidado: Si).")
        try:
            # 1. Seleccionar Concepto = "Pedido" (valor "4" en el select #cboConcepto)
            self.page.select_option("#cboConcepto", "4")
            # Forzar evento de cambio en jQuery
            self.page.evaluate("$('#cboConcepto').trigger('change')")

            # 2. Seleccionar Consolidado = "Si" (valor "1" en el select #cboConsolidado)
            self.page.select_option("#cboConsolidado", "1")

            self._verificar_reset()
            self.verificar_pausa()

            # 3. Hacer clic en "Consultar" (#btnBuscar)
            self.page.wait_for_selector("#btnBuscar", state="visible", timeout=15000)
            self.page.click("#btnBuscar")
            self.page.wait_for_load_state("networkidle")

            self._verificar_reset()
            self.verificar_pausa()

            # Obtener el directorio raíz del proyecto donde reside gui.py
            if getattr(sys, 'frozen', False):
                root_dir = os.path.dirname(os.path.abspath(sys.executable))
            else:
                root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            dest_path = os.path.join(root_dir, "reporte_pedidos.xlsx")
            self.log(f"[PEDIDOS] Iniciando descarga del archivo Excel en: {dest_path}")

            # 4. Hacer clic en "Descargar Excel" y guardar en la raíz
            with self.page.expect_download(timeout=60000) as dl:
                self.page.click("#btnDownloadExcel")
            download = dl.value
            
            try:
                download.save_as(dest_path)
                self.log(f"[PEDIDOS] ✔ Descarga de Pedidos finalizada correctamente.")
            except Exception as e:
                if "Permission" in str(e) or "denied" in str(e) or "Errno 13" in str(e):
                    self.log("[WARN] El archivo 'reporte_pedidos.xlsx' está bloqueado (posiblemente abierto en Excel).")
                    alt_path = os.path.join(root_dir, "reporte_pedidos_NUEVO.xlsx")
                    self.log(f"[PEDIDOS] Guardando descarga alternativa en: {alt_path}")
                    download.save_as(alt_path)
                    self.log(f"[PEDIDOS] ✔ Descarga de Pedidos finalizada de forma alternativa.")
                else:
                    raise

        except Exception as e:
            self.log(f"[ERROR] Ocurrió un fallo en el proceso de descarga: {e}")
