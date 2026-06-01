# utils/login.py
from utils.network import navegar_con_red

def login_nodo(page, user, password, log_fn, stop_event=None, reset_event=None):
    if not navegar_con_red(page, "https://nodo-practical.nodosolutions.com/", log_fn, stop_event, reset_event):
        return False
    try:
        page.wait_for_selector("#Correo", timeout=5000)
        page.fill("#Correo", user)
        page.fill("#txtClave", password)
        page.evaluate("document.getElementById('chkMantenerSesion').click()")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        log_fn("[AUTH] Login NODO exitoso.")
    except Exception:
        log_fn("[AUTH] Sesión NODO ya activa.")
    return True