# sync_main.py
from playwright.sync_api import sync_playwright
from utils.credentials import cargar_credenciales
from utils.login import login_nodo
from modules.sync_pedidos import SincronizadorPedidos

TIMEOUT_NAVEGACION = 45000

import os, sys

if getattr(sys, 'frozen', False):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(
        sys._MEIPASS, "ms-playwright"
    )

def run_sincronizar(log_fn, stop_event=None, reset_event=None):
    log_fn("[INFO] Iniciando pipeline de descarga (Esqueleto NODO).")

    nodo_user, nodo_pass = cargar_credenciales(log_fn)
    if not all([nodo_user, nodo_pass]):
        log_fn("[ERROR] Abortando: Credenciales de NODO faltantes o incompletas.")
        return

    creds_dict = {
        'nodo_user': nodo_user,
        'nodo_pass': nodo_pass
    }

    with sync_playwright() as p:
        log_fn("[INFO] Inicializando entorno de navegación Chromium.")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_navigation_timeout(TIMEOUT_NAVEGACION)

        try:
            if reset_event and reset_event.is_set():
                raise KeyboardInterrupt("Reinicio forzado")

            # ── Login para toda la sesión ──────────────────
            log_fn("[AUTH] Autenticando en NODO.")
            if not login_nodo(page, nodo_user, nodo_pass, log_fn, stop_event, reset_event):
                log_fn("[ERROR] No se pudo autenticar en NODO. Abortando.")
                return

            if reset_event and reset_event.is_set():
                raise KeyboardInterrupt("Reinicio forzado")

            # Paso 1: Pedidos (Descarga de informe)
            pedidos_worker = SincronizadorPedidos(page, log_fn, stop_event, reset_event)
            pedidos_worker.sincronizar(creds_dict)
            
            log_fn("\n[✔] PIPELINE GLOBAL FINALIZADO DE FORMA EXITOSA.")

        except KeyboardInterrupt:
            log_fn("\n[AVISO] Proceso abortado o reiniciado por el usuario.")
        except Exception as e:
            log_fn(f"\n[ERROR CRÍTICO] Error en el orquestador central: {e}")
        finally:
            context.close()
            browser.close()