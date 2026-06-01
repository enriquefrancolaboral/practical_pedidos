# data/servicio_nodo.py
from playwright.sync_api import sync_playwright
from typing import Callable, Optional, Dict, Any
from threading import Event
from core.modelos import Pedido, Credenciales
import pandas as pd
import os
import sys
import tempfile
from datetime import datetime, timedelta

# Fecha base fija para ordenamiento cuando el Excel no tiene columna Fecha.
# Pedidos con índice mayor → fecha más reciente → aparecen primero en la UI.
_FECHA_BASE = datetime(2000, 1, 1)


class ServicioNodo:
    """Conexión con el sistema NODO para sincronizar pedidos"""

    def __init__(self, credenciales: Credenciales, log_fn: Optional[Callable] = None):
        self.credenciales = credenciales
        self.log = log_fn or print
        self._stop_event = Event()
        self._reset_event = Event()

    def _login_nodo(self, page) -> bool:
        """Autentica en NODO y valida si las credenciales son correctas."""
        try:
            self.log("[AUTH] Autenticando en NODO...")
            page.goto(self.credenciales.servidor, timeout=45000)
            page.wait_for_selector("#Correo", timeout=5000)
            page.fill("#Correo", self.credenciales.usuario)
            page.fill("#txtClave", self.credenciales.password)
            page.evaluate("document.getElementById('chkMantenerSesion').click()")
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle", timeout=10000)

            error_usuario = page.query_selector(
                ".alert.alert-danger:has-text('No se ha encontrado un usuario registrado')"
            )
            error_pass = page.query_selector(
                ".alert.alert-danger:has-text('La contraseña ingresada es incorrecta')"
            )

            if error_usuario or error_pass:
                mensaje = "Usuario no encontrado" if error_usuario else "Contraseña incorrecta"
                self.log(f"[AUTH] Error de autenticación: {mensaje}")
                return False

            if "Login" in page.title() or page.url == self.credenciales.servidor:
                self.log("[AUTH] Credenciales inválidas, se mantuvo en página de login.")
                return False

            self.log("[AUTH] Login exitoso")
            return True
        except Exception as e:
            self.log(f"[AUTH] Error durante el proceso de login: {e}")
            return False

    def sincronizar_pedidos(self) -> Dict[str, Any]:
        """Sincroniza pedidos desde NODO usando un archivo temporal."""
        resultado = {"exito": False, "mensaje": "", "pedidos": None}
        temp_path = None

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            try:
                if not self._login_nodo(page):
                    resultado["mensaje"] = "Error de autenticación. Verifique usuario/contraseña."
                    return resultado

                self.log("[PEDIDOS] Navegando a Libro de Ventas...")
                page.goto(f"{self.credenciales.servidor}/LibroVenta/Index", timeout=45000)
                page.wait_for_load_state("networkidle")

                self.log("[PEDIDOS] Aplicando filtros...")
                page.select_option("#cboConcepto", "4")
                page.evaluate("$('#cboConcepto').trigger('change')")
                page.select_option("#cboConsolidado", "1")

                self.log("[PEDIDOS] Ejecutando consulta...")
                page.click("#btnBuscar")
                page.wait_for_load_state("networkidle")

                with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
                    temp_path = tmp_file.name
                    self.log(f"[PEDIDOS] Archivo temporal: {temp_path}")

                self.log("[PEDIDOS] Descargando reporte...")
                with page.expect_download(timeout=60000) as dl:
                    page.click("#btnDownloadExcel")
                dl.value.save_as(temp_path)
                self.log("[PEDIDOS] Descarga completada")

                self.log("[PEDIDOS] Procesando datos...")
                df = pd.read_excel(temp_path)
                tiene_fecha = 'Fecha' in df.columns

                pedidos = []
                for idx, (_, row) in enumerate(df.iterrows()):
                    # --- CORRECCIÓN RF-10 ---
                    # Si el Excel tiene columna Fecha real, usarla.
                    # Si no, asignar fechas incrementales desde una base fija para que
                    # el índice de fila determine el orden (más alto = más reciente).
                    fecha_pedido = _FECHA_BASE + timedelta(seconds=idx)
                    if tiene_fecha and pd.notna(row.get('Fecha')):
                        try:
                            fecha_pedido = pd.to_datetime(row['Fecha']).to_pydatetime()
                        except Exception:
                            pass  # Mantener el valor incremental como fallback

                    pedido = Pedido(
                        numero_pedido=str(row.get('Factura', '')),
                        fecha=fecha_pedido,
                        estado=str(row.get('EstadoTransaccion', '')),
                        total=float(row.get('Total', 0)) if pd.notna(row.get('Total')) else 0.0,
                        cliente=str(row.get('Cliente', '')),
                        vendedor=str(row.get('Vendedor', '')),
                        moneda=str(row.get('Moneda', '')) if pd.notna(row.get('Moneda')) else "",
                    )
                    pedidos.append(pedido)

                # NO invertir aquí: _actualizar_tabla en app.py ordena por fecha desc.
                self.log(f"[PEDIDOS] Procesados {len(pedidos)} pedidos")

                resultado["exito"] = True
                resultado["mensaje"] = "Descarga y procesamiento exitoso"
                resultado["pedidos"] = pedidos

            except Exception as e:
                resultado["mensaje"] = f"Error: {str(e)}"
                self.log(f"[ERROR] {e}")
            finally:
                # RF-33: eliminar archivo temporal siempre
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                        self.log("[LIMPIAR] Archivo temporal eliminado.")
                    except Exception as e:
                        self.log(f"[LIMPIAR] Error al eliminar archivo temporal: {e}")

                context.close()
                browser.close()
                self.log("[PEDIDOS] Navegador cerrado")

        return resultado

    def probar_conexion(self) -> Dict[str, Any]:
        """Prueba de conexión sin descargar datos."""
        resultado = {"exito": False, "mensaje": ""}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            try:
                if self._login_nodo(page):
                    resultado["exito"] = True
                    resultado["mensaje"] = "Conexión exitosa"
                else:
                    resultado["mensaje"] = "Error de autenticación. Verifique usuario/contraseña."
            except Exception as e:
                resultado["mensaje"] = f"Error de conexión: {str(e)}"
            finally:
                context.close()
                browser.close()

        return resultado
