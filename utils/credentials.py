# utils/credentials.py
import sys
import keyring

SERVICE_NODO  = "practical_sync_nodo"
SERVICE_DIGIP = "practical_sync_digip"

KEY_USER = "username"
KEY_PASS = "password"


def guardar_credenciales(nodo_user: str, nodo_pass: str,
                          digip_user: str, digip_pass: str,
                          log_fn=None) -> bool:
    """Guarda las cuatro credenciales en el Windows Credential Manager."""
    try:
        keyring.set_password(SERVICE_NODO,  KEY_USER, nodo_user)
        keyring.set_password(SERVICE_NODO,  KEY_PASS, nodo_pass)
        keyring.set_password(SERVICE_DIGIP, KEY_USER, digip_user)
        keyring.set_password(SERVICE_DIGIP, KEY_PASS, digip_pass)
        if log_fn:
            log_fn("[INFO] Credenciales guardadas correctamente en el sistema.")
        return True
    except Exception as e:
        if log_fn:
            log_fn(f"[ERROR] No se pudieron guardar las credenciales: {e}")
        return False


def cargar_credenciales(log_fn):
    """Carga las credenciales desde el Windows Credential Manager."""
    try:
        nodo_user  = keyring.get_password(SERVICE_NODO,  KEY_USER)
        nodo_pass  = keyring.get_password(SERVICE_NODO,  KEY_PASS)
        digip_user = keyring.get_password(SERVICE_DIGIP, KEY_USER)
        digip_pass = keyring.get_password(SERVICE_DIGIP, KEY_PASS)
    except Exception as e:
        log_fn(f"[ERROR] Error al acceder al almacén de credenciales: {e}")
        return None, None, None, None

    if not all([nodo_user, nodo_pass, digip_user, digip_pass]):
        log_fn("[ERROR] Credenciales no configuradas.")
        log_fn("[SOLUCIÓN] Usa el botón 'Configurar Credenciales' en la aplicación.")
        return None, None, None, None

    log_fn("[INFO] Credenciales cargadas correctamente.")
    return nodo_user, nodo_pass, digip_user, digip_pass


def credenciales_configuradas() -> bool:
    """Retorna True si las cuatro credenciales están presentes en el vault."""
    try:
        return all([
            keyring.get_password(SERVICE_NODO,  KEY_USER),
            keyring.get_password(SERVICE_NODO,  KEY_PASS),
            keyring.get_password(SERVICE_DIGIP, KEY_USER),
            keyring.get_password(SERVICE_DIGIP, KEY_PASS),
        ])
    except Exception:
        return False
