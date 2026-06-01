# sync_main.py
from playwright.sync_api import sync_playwright
from utils.credentials import cargar_credenciales

from modules.sync_articulos import SincronizadorArticulos
from modules.sync_clientes import SincronizadorClientes
from modules.sync_pedidos import SincronizadorPedidos

from utils.login import login_nodo, login_digip

TIMEOUT_NAVEGACION = 45000

import os, sys

if getattr(sys, 'frozen', False):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
        sys._MEIPASS, "ms-playwright"
    )

def run_sincronizar(log_fn, stop_event=None, reset_event=None,
                    sync_articulos_v=True, sync_clientes_v=True, sync_pedidos_v=True):
    log_fn("[INFO] Iniciando pipeline de sincronización modular global.")

    nodo_user, nodo_pass, digip_user, digip_pass = cargar_credenciales(log_fn)
    if not all([nodo_user, nodo_pass, digip_user, digip_pass]):
        log_fn("[ERROR] Abortando: Credenciales faltantes en el entorno.")
        return

    creds_dict = {
        'nodo_user': nodo_user, 'nodo_pass': nodo_pass,
        'digip_user': digip_user, 'digip_pass': digip_pass
    }

    with sync_playwright() as p:
        log_fn("[INFO] Inicializando entorno de navegación Chromium.")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_navigation_timeout(TIMEOUT_NAVEGACION)

        try:
            # ── Login único para toda la sesión ──────────────────
            log_fn("[AUTH] Autenticando en ambos sistemas.")
            if not login_nodo(page, nodo_user, nodo_pass, log_fn, stop_event, reset_event):
                log_fn("[ERROR] No se pudo autenticar en NODO. Abortando.")
                return
            if not login_digip(page, digip_user, digip_pass, log_fn, stop_event, reset_event):
                log_fn("[ERROR] No se pudo autenticar en DIGIP. Abortando.")
                return
                
            # Paso 1: Artículos
            if reset_event and reset_event.is_set():
                raise KeyboardInterrupt("Reinicio forzado")
            if sync_articulos_v:
                articulos_worker = SincronizadorArticulos(page, log_fn, stop_event, reset_event)
                articulos_worker.sincronizar(creds_dict)
            else:
                log_fn("[SKIP] Paso 1/3 (Artículos) deshabilitado.")

            # Paso 2: Clientes
            if reset_event and reset_event.is_set():
                raise KeyboardInterrupt("Reinicio forzado")
            if sync_clientes_v:
                clientes_worker = SincronizadorClientes(page, log_fn, stop_event, reset_event)
                clientes_worker.sincronizar(creds_dict)
            else:
                log_fn("[SKIP] Paso 2/3 (Clientes) deshabilitado.")

            # Paso 3: Pedidos
            if reset_event and reset_event.is_set():
                raise KeyboardInterrupt("Reinicio forzado")
            if sync_pedidos_v:
                pedidos_worker = SincronizadorPedidos(page, log_fn, stop_event, reset_event)
                pedidos_worker.sincronizar(creds_dict)
            else:
                log_fn("[SKIP] Paso 3/3 (Pedidos) deshabilitado.")

            log_fn("\n[✔] PIPELINE GLOBAL FINALIZADO DE FORMA EXITOSA.")

        except KeyboardInterrupt:
            log_fn("\n[AVISO] Proceso abortado o reiniciado por el usuario.")
        except Exception as e:
            log_fn(f"\n[ERROR CRÍTICO] Error en el orquestador central: {e}")
        finally:
            context.close()
            browser.close()