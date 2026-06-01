# utils/network.py
import socket
import time

def hay_conexion_internet():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        return False

def esperar_conexion_red(log_fn, stop_event=None, reset_event=None):
    if hay_conexion_internet():
        return True

    log_fn("\n[RED] Conexión perdida. Esperando recuperación.")
    tiempo_espera = 0

    while not hay_conexion_internet():
        if reset_event and reset_event.is_set():
            return False
        if stop_event and stop_event.is_set():
            while stop_event.is_set():
                if reset_event and reset_event.is_set():
                    return False
                stop_event.wait(1)
        time.sleep(5)
        tiempo_espera += 5
        if tiempo_espera % 30 == 0:
            log_fn(f"[RED] Esperando. ({tiempo_espera}s)")

    log_fn(f"[RED] Conexión recuperada después de {tiempo_espera}s")
    return True

def navegar_con_red(page, url, log_fn, stop_event=None, reset_event=None, timeout=45000):
    while True:
        # Verificar reset antes de cada intento de navegación
        if reset_event and reset_event.is_set():
            return False
        try:
            log_fn(f"  → Navegando a: {url[:80]}")
            page.goto(url, timeout=timeout)
            page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except Exception as e:
            error_msg = str(e)
            if "ERR_INTERNET_DISCONNECTED" in error_msg or "net::ERR_" in error_msg or "Timeout" in error_msg:
                if not esperar_conexion_red(log_fn, stop_event, reset_event):
                    return False
                continue
            raise