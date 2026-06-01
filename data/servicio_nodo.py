# data/servicio_nodo.py
from playwright.sync_api import sync_playwright
from typing import Callable, Optional, Dict, Any
from threading import Event
from core.modelos import Pedido, Credenciales
import pandas as pd
import os
import sys
import tempfile
from datetime import datetime

class ServicioNodo:
    """Conexión con el sistema NODO para sincronizar pedidos"""
    
    def __init__(self, credenciales: Credenciales, log_fn: Optional[Callable] = None):
        self.credenciales = credenciales
        self.log = log_fn or print
        self._stop_event = Event()
        self._reset_event = Event()
        
    def _get_root_dir(self):
        """Obtiene el directorio raíz del proyecto"""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
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
            
            # Esperar a que la página cargue después del login
            page.wait_for_load_state("networkidle", timeout=10000)
            
            # --- VALIDACIÓN DE ERRORES ---
            # Buscar mensajes de error en la página actual
            error_usuario = page.query_selector(".alert.alert-danger:has-text('No se ha encontrado un usuario registrado')")
            error_pass = page.query_selector(".alert.alert-danger:has-text('La contraseña ingresada es incorrecta')")
            
            if error_usuario or error_pass:
                mensaje = "Usuario no encontrado" if error_usuario else "Contraseña incorrecta"
                self.log(f"[AUTH] Error de autenticación: {mensaje}")
                return False
                
            # Verificar si redirigió a una página de dashboard o similar
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
        resultado = {"exito": False, "mensaje": "", "archivo": None, "pedidos": None}
        temp_path = None
        
        with sync_playwright() as p:
            # Usar headless=True para producción, False para debug
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            try:
                # Login
                if not self._login_nodo(page):
                    resultado["mensaje"] = "Error de autenticación. Verifique usuario/contraseña."
                    return resultado
                
                self.log("[PEDIDOS] Navegando a Libro de Ventas...")
                page.goto(f"{self.credenciales.servidor}/LibroVenta/Index", timeout=45000)
                page.wait_for_load_state("networkidle")
                
                # Aplicar filtros
                self.log("[PEDIDOS] Aplicando filtros...")
                page.select_option("#cboConcepto", "4")  # Pedido
                page.evaluate("$('#cboConcepto').trigger('change')")
                page.select_option("#cboConsolidado", "1")  # Sí
                
                # Consultar
                self.log("[PEDIDOS] Ejecutando consulta...")
                page.click("#btnBuscar")
                page.wait_for_load_state("networkidle")
                
                # --- USAR ARCHIVO TEMPORAL ---
                # Crear archivo temporal con sufijo .xlsx
                with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
                    temp_path = tmp_file.name
                    self.log(f"[PEDIDOS] Archivo temporal creado: {temp_path}")
                
                # Descargar el archivo
                self.log("[PEDIDOS] Descargando reporte de pedidos...")
                with page.expect_download(timeout=60000) as dl:
                    page.click("#btnDownloadExcel")
                download = dl.value
                download.save_as(temp_path)  # Guardar en el archivo temporal
                self.log("[PEDIDOS] Descarga completada")
                
                # Leer el archivo temporal con pandas
                self.log("[PEDIDOS] Procesando datos...")
                df = pd.read_excel(temp_path)
                
                # Procesar el DataFrame para crear los objetos Pedido
                pedidos = []
                for _, row in df.iterrows():
                    # Intentar obtener la fecha del pedido si existe, sino usar datetime.now()
                    fecha_pedido = datetime.now()
                    try:
                        if 'Fecha' in df.columns and pd.notna(row.get('Fecha')):
                            fecha_pedido = pd.to_datetime(row.get('Fecha'))
                    except:
                        pass
                    
                    pedido = Pedido(
                        numero_pedido=str(row.get('Factura', '')),
                        fecha=fecha_pedido,
                        estado=str(row.get('EstadoTransaccion', '')),
                        total=float(row.get('Total', 0)) if pd.notna(row.get('Total')) else 0,
                        cliente=str(row.get('Cliente', '')),
                        vendedor=str(row.get('Vendedor', '')),
                        moneda=str(row.get('Moneda', '')) if pd.notna(row.get('Moneda')) else ""
                    )
                    pedidos.append(pedido)
                
                # INVERTIR EL ORDEN: los pedidos más nuevos (últimos en el Excel) aparecerán primero
                # Esto cumple con RF-10
                pedidos.reverse()
                self.log(f"[PEDIDOS] Procesados {len(pedidos)} pedidos")
                
                resultado["exito"] = True
                resultado["mensaje"] = "Descarga y procesamiento exitoso"
                resultado["pedidos"] = pedidos
                
            except Exception as e:
                resultado["mensaje"] = f"Error: {str(e)}"
                self.log(f"[ERROR] {e}")
            finally:
                # --- LIMPIEZA DEL ARCHIVO TEMPORAL (RF-33) ---
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                        self.log("[LIMPIAR] Archivo temporal eliminado correctamente.")
                    except Exception as e:
                        self.log(f"[LIMPIAR] Error al eliminar archivo temporal: {e}")
                
                # Cerrar el navegador
                context.close()
                browser.close()
                self.log("[PEDIDOS] Navegador cerrado")
        
        return resultado
    
    def probar_conexion(self) -> Dict[str, Any]:
        """Prueba de conexión para verificar credenciales sin descargar datos"""
        resultado = {"exito": False, "mensaje": ""}
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            try:
                if not self._login_nodo(page):
                    resultado["mensaje"] = "Error de autenticación. Verifique usuario/contraseña."
                else:
                    resultado["exito"] = True
                    resultado["mensaje"] = "Conexión exitosa"
            except Exception as e:
                resultado["mensaje"] = f"Error de conexión: {str(e)}"
            finally:
                context.close()
                browser.close()
        
        return resultado