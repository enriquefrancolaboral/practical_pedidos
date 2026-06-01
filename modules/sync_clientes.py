# modules/sync_clientes.py
from modules.base import BaseSincronizador
from utils.network import navegar_con_red

import pandas as pd
import os
import time
import tempfile

# ── URLs ──────────────────────────────────────────────────────────────────────
NODO_LOGIN_URL     = "https://nodo-practical.nodosolutions.com/"
NODO_CLIENTES_URL  = "https://nodo-practical.nodosolutions.com/PersonaNegocio/Index"

DIGIP_LOGIN_URL    = "https://app.digipwms.com/login"
DIGIP_HOME_URL     = "https://app.digipwms.com/home"
DIGIP_CLIENTES_URL = "https://app.digipwms.com/Configuracion/Cliente"

# Columnas esperadas del Excel de NODO (fila 1 = encabezado)
NODO_COLUMNS = ['Id', 'Acciones', 'Tipo', 'Nº', 'Razón Social',
                 'Dirección', 'Teléfono', 'Email', 'Rol', 'Vendedor', 'Estado']

WAIT_MODAL  = 800
WAIT_ACTION = 500

PRIORIDAD_MAP = {
    "0": "0", "10": "10", "20": "20", "30": "30", "40": "40", "50": "50",
    "Urgente": "10", "Alta": "20", "Media": "30", "Baja": "40", "Muy Baja": "50",
}


class SincronizadorClientes(BaseSincronizador):
    """
    Flujo completo de sincronización de clientes:
      (1) Login en NODO + descarga del Excel de personas/negocios.
      (2) Login en DIGIP + descarga del Excel de clientes existentes.
      (3) Cruce: detectar clientes de NODO ausentes en DIGIP.
      (4) Carga secuencial en DIGIP vía modal 'Nuevo Cliente'.
      (5) Carga de dirección/ubicación para cada cliente recién creado.
      (6) Limpieza de archivos temporales.
    """

    def _verificar_reset(self):
        """Lanza KeyboardInterrupt si se solicitó reinicio."""
        if self.reset_event and self.reset_event.is_set():
            raise KeyboardInterrupt("Reinicio forzado")

    def sincronizar(self, credenciales_dict):
        if not credenciales_dict:
            self.log("[ERROR] No se recibieron credenciales para el módulo de Clientes.")
            return 0, 0

        nodo_user  = credenciales_dict.get('nodo_user')
        nodo_pass  = credenciales_dict.get('nodo_pass')
        digip_user = credenciales_dict.get('digip_user')
        digip_pass = credenciales_dict.get('digip_pass')

        temp_nodo  = None
        temp_digip = None

        self.log(f"\n{'='*50}")
        self.log("SINCRONIZACIÓN DE CLIENTES")
        self.log(f"{'='*50}")

        try:
            # ── (1) Descarga NODO ────────────────────────────────────
            self._verificar_reset()
            self.verificar_pausa()
            temp_nodo = self._descargar_nodo(nodo_user, nodo_pass)
            if temp_nodo is None:
                self.log("[CLIENTES] No se pudo obtener el Excel de NODO. Abortando.")
                return 0, 0

            # ── (2) Descarga DIGIP ───────────────────────────────────
            self._verificar_reset()
            self.verificar_pausa()
            temp_digip = self._descargar_digip(digip_user, digip_pass)
            if temp_digip is None:
                self.log("[CLIENTES] No se pudo obtener el Excel de DIGIP. Abortando.")
                return 0, 0

            # ── (3) Cruce ────────────────────────────────────────────
            self._verificar_reset()
            self.verificar_pausa()
            df_faltantes = self._cruzar(temp_nodo, temp_digip)
            if df_faltantes is None or df_faltantes.empty:
                self.log("[CLIENTES] No hay clientes nuevos para cargar.")
                return 0, 0

            self.log(f"[CLIENTES] {len(df_faltantes)} clientes a cargar en DIGIP.")

            # ── (4) y (5) Carga de clientes + direcciones ────────────
            self._verificar_reset()
            self.verificar_pausa()
            ok, skip = self._cargar_en_digip(df_faltantes)
            return ok, skip

        finally:
            # ── (6) Limpieza ─────────────────────────────────────────
            for path in (temp_nodo, temp_digip):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                        self.log(f"[INFO] Temporal eliminado: {path}")
                    except Exception as e:
                        self.log(f"[WARN] No se pudo eliminar {path}: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # DESCARGA NODO
    # ──────────────────────────────────────────────────────────────────────────

    def _descargar_nodo(self, user, password) -> str | None:
        
        self._verificar_reset()
        self.verificar_pausa()
        
        if not navegar_con_red(self.page, NODO_CLIENTES_URL, self.log, self.stop_event, self.reset_event):
            return None

        self._verificar_reset()
        self.verificar_pausa()
        temp_path = os.path.join(tempfile.gettempdir(), f"nodo_clientes_{int(time.time())}.xlsx")
        try:
            with self.page.expect_download(timeout=60000) as dl:
                self.page.click("button.buttons-excel")
            dl.value.save_as(temp_path)
            self.log(f"[CLIENTES] Excel NODO descargado: {temp_path}")
            return temp_path
        except Exception as e:
            self.log(f"[ERROR] No se pudo descargar el Excel de NODO: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # DESCARGA DIGIP
    # ──────────────────────────────────────────────────────────────────────────

    def _descargar_digip(self, user, password) -> str | None:
        
        self._verificar_reset()
        self.verificar_pausa()
        
        if not navegar_con_red(self.page, DIGIP_CLIENTES_URL, self.log, self.stop_event, self.reset_event):
            return None

        self._verificar_reset()
        self.verificar_pausa()
        try:
            self.page.click("button.dropdown-toggle")
            self.page.wait_for_selector("a.dropdown-item[href*='ExcelClientes']", state="visible")
            with self.page.expect_download(timeout=60000) as dl:
                self.page.click("a.dropdown-item[href*='ExcelClientes']")
            download = dl.value
            temp_path = os.path.join(tempfile.gettempdir(), download.suggested_filename)
            download.save_as(temp_path)
            self.log(f"[CLIENTES] CSV DIGIP descargado: {temp_path}")
            return temp_path
        except Exception as e:
            self.log(f"[ERROR] No se pudo descargar el Excel de DIGIP: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # CRUCE
    # ──────────────────────────────────────────────────────────────────────────

    def _cruzar(self, nodo_path: str, digip_path: str) -> pd.DataFrame | None:
        self.log("[CLIENTES] (3) Cruzando listas.")
        try:
            xlsx = pd.read_excel(nodo_path, header=1)
            xlsx.columns = NODO_COLUMNS

            digip_df = pd.read_csv(digip_path, encoding='latin-1', sep=None, engine='python')

            digip_df['Codigo'] = (
                digip_df['Codigo'].astype(str)
                .str.replace('.0', '', regex=False)
                .str.strip()
            )

            xlsx['Id'] = xlsx['Id'].astype(str).str.strip()

            resultado = xlsx.merge(
                digip_df[['Codigo']],
                left_on='Id', right_on='Codigo', how='left'
            )
            faltantes = (
                resultado[resultado['Codigo'].isna()]
                .drop(columns=['Codigo'])
                .copy()
            )
            faltantes = faltantes.astype(str).replace(
                {'nan': '', 'NaN': '', 'None': '', '<NA>': ''}
            )

            self.log(f"[CLIENTES] Faltantes detectados: {len(faltantes)}")
            return faltantes

        except Exception as e:
            self.log(f"[ERROR] Error durante el cruce: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # CARGA EN DIGIP
    # ──────────────────────────────────────────────────────────────────────────

    def _cargar_en_digip(self, df: pd.DataFrame):
        self.log("[CLIENTES] (4) Iniciando carga en DIGIP.")

        self._verificar_reset()
        if not navegar_con_red(self.page, DIGIP_CLIENTES_URL, self.log, self.stop_event, self.reset_event):
            return 0, 0

        ok_count   = 0
        skip_count = 0
        total      = len(df)

        for i, (_, row) in enumerate(df.iterrows()):
            # ── Puntos de control al inicio de cada iteración ────────
            self._verificar_reset()
            self.verificar_pausa()
            self._verificar_reset()  # Re-verificar tras salir de pausa

            codigo       = str(row.get('Id',           '') or '').strip()
            razon_social = str(row.get('Razón Social', '') or '').strip()
            fiscal       = str(row.get('Nº',           '') or '').strip()
            direccion    = str(row.get('Dirección',    '') or '').strip()
            telefono     = str(row.get('Teléfono',     '') or '').strip()

            self.log(f"  [{i+1}/{total}] {codigo} - {razon_social}")

            if not codigo or not razon_social:
                self.log(f"    [WARN] Fila sin código o razón social. Se omite.")
                skip_count += 1
                continue

            # ── Asegurar estar en la página de clientes ─────────────
            try:
                current_url = self.page.url
                if DIGIP_CLIENTES_URL not in current_url:
                    self._verificar_reset()
                    if not navegar_con_red(self.page, DIGIP_CLIENTES_URL, self.log, self.stop_event, self.reset_event):
                        skip_count += 1
                        continue
            except Exception:
                pass

            try:
                # (4a) Abrir modal Nuevo Cliente
                self._abrir_modal_nuevo()

                # Verificar reset tras la espera del modal (WAIT_MODAL)
                self._verificar_reset()

                # (4b) Rellenar y guardar
                resultado = self._cargar_cliente(codigo, razon_social, fiscal)

                if resultado == "ok":
                    ok_count += 1
                    self.log(f"    ✔ Cliente guardado correctamente.")

                    # (5) Cargar dirección inmediatamente
                    self._verificar_reset()
                    self._cargar_direccion_cliente(codigo, razon_social, direccion, fiscal, telefono)

                else:
                    skip_count += 1
                    self.log(f"    ~ Saltado (ya existe o error).")

                self.page.wait_for_timeout(WAIT_ACTION)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                self.log(f"    [ERROR] {e}")
                self._intentar_cerrar_modal("#ModalInfo")
                skip_count += 1

        self.log(f"\n[CLIENTES] RESUMEN: {ok_count} cargados | {skip_count} saltados | {total} total.")
        return ok_count, skip_count

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS MODAL CLIENTE
    # ──────────────────────────────────────────────────────────────────────────

    def _abrir_modal_nuevo(self):
        self.page.locator("button:has-text('Opciones')").click()
        nuevo = self.page.locator("a.dropdown-item:has-text('Nuevo')")
        nuevo.wait_for(state="visible", timeout=5000)
        nuevo.click()
        modal = self.page.locator("#ModalInfo")
        modal.wait_for(state="visible", timeout=10000)
        self.page.locator("#ModalInfo #Codigo").wait_for(state="visible", timeout=5000)
        self.page.wait_for_timeout(WAIT_MODAL)

    def _cargar_cliente(self, codigo: str, razon_social: str, fiscal: str) -> str:
        modal = self.page.locator("#ModalInfo")
        modal.locator("#Codigo").fill(codigo)
        modal.locator("#Descripcion").fill(razon_social)
        modal.locator("#IdentificadorFiscal").fill(fiscal or codigo)
        modal.locator("#MinimoDiasVencimiento").fill("30")
        modal.locator("#Prioridad").select_option("30")  # Media

        # Checkbox Activo → asegurar marcado
        cb = modal.locator("#Activo")
        if not cb.is_checked():
            modal.locator("label.checkbox-checked:has(#Activo)").click()

        # Guardar
        modal.locator("input[type='submit'][value='Guardar']").click()

        try:
            self.page.wait_for_selector(".swal2-popup", timeout=6000)
            titulo = self.page.locator("#swal2-title").inner_text().strip()
            self.page.locator(".swal2-confirm").click()
            self.page.wait_for_timeout(400)

            if "Buen Trabajo" in titulo:
                self.page.locator("#ModalInfo").wait_for(state="hidden", timeout=5000)
                return "ok"
            else:
                self._intentar_cerrar_modal("#ModalInfo")
                return "skip"
        except Exception:
            self._intentar_cerrar_modal("#ModalInfo")
            return "skip"

    # ──────────────────────────────────────────────────────────────────────────
    # CARGA DE DIRECCIÓN
    # ──────────────────────────────────────────────────────────────────────────

    def _cargar_direccion_cliente(self, codigo: str, razon_social: str,
                                   direccion: str, fiscal: str, telefono: str):
        """
        Navega a la página del cliente recién creado y carga la primera ubicación.
        """
        self.log(f"    → Cargando dirección para cliente {codigo}.")
        try:
            self._verificar_reset()
            url_busqueda = f"{DIGIP_CLIENTES_URL}?ClienteCodigo={codigo}"
            if not navegar_con_red(self.page, url_busqueda, self.log, self.stop_event, self.reset_event):
                self.log(f"    [WARN] No se pudo navegar para cargar dirección de {codigo}.")
                return

            self._verificar_reset()
            self.verificar_pausa()
            self._verificar_reset()  # Re-verificar tras salir de pausa

            # Buscar el enlace de Ubicación en la tabla
            ubicacion_link = self.page.locator(
                "a[href*='clienteUbicacion?clienteId']"
            ).first
            ubicacion_link.wait_for(state="visible", timeout=10000)
            href = ubicacion_link.get_attribute("href")
            self.log(f"    → Enlace de ubicación: {href}")
            ubicacion_link.click()
            self.page.wait_for_load_state("networkidle")

            self._verificar_reset()

            # Verificar si ya tiene direcciones cargadas
            filas = self.page.locator("table.table tbody tr")
            tiene_datos = False
            for j in range(filas.count()):
                texto = filas.nth(j).inner_text().strip()
                if texto:
                    tiene_datos = True
                    break

            if tiene_datos:
                self.log(f"    [SKIP] Cliente {codigo} ya tiene dirección. Se omite.")
                return

            # Abrir modal de nueva ubicación
            self.page.locator(
                "button.dropdown-toggle:has-text('Opciones')"
            ).first.click()
            nuevo_link = self.page.locator(
                "a[href*='clienteUbicacion/CrearEditar'][title='Nuevo']"
            ).first
            nuevo_link.wait_for(state="visible", timeout=8000)
            nuevo_link.click()

            modal_ub = self.page.locator("#ModalInformacion")
            modal_ub.wait_for(state="visible", timeout=10000)
            self.page.locator("#ModalInformacion #Descripcion").wait_for(
                state="visible", timeout=8000
            )
            self.page.wait_for_timeout(WAIT_MODAL)

            # Verificar reset tras la espera del modal
            self._verificar_reset()

            # Rellenar campos de ubicación
            self.page.locator("#ModalInformacion #Descripcion").fill(razon_social)
            if direccion:
                self.page.locator("#ModalInformacion #pac-input").fill(direccion)
            if fiscal:
                self.page.locator("#ModalInformacion #Codigo").fill(fiscal)
            if telefono:
                self.page.locator("#ModalInformacion #InformacionEntrega").fill(telefono)

            # Checkbox Activo ubicación
            cb_ub = self.page.locator("#ModalInformacion #Activo")
            if not cb_ub.is_checked():
                self.page.locator(
                    "#ModalInformacion label.checkbox-checked:has(#Activo)"
                ).click()

            # Guardar
            self.page.locator(
                "#ModalInformacion input[type='submit'][value='Guardar']"
            ).click()

            try:
                self.page.locator("#ModalInformacion").wait_for(
                    state="hidden", timeout=6000
                )
                self.log(f"    ✔ Dirección cargada para {codigo}.")
            except Exception:
                self._intentar_cerrar_modal("#ModalInformacion")
                self.log(f"    [WARN] Modal de dirección no se cerró solo para {codigo}.")

        except KeyboardInterrupt:
            raise
        except Exception as e:
            self.log(f"    [ERROR] Error al cargar dirección de {codigo}: {e}")
            self._intentar_cerrar_modal("#ModalInformacion")

    # ──────────────────────────────────────────────────────────────────────────
    # HELPER GENERAL
    # ──────────────────────────────────────────────────────────────────────────

    def _intentar_cerrar_modal(self, selector: str):
        try:
            close_btn = self.page.locator(f"{selector} .close")
            if close_btn.is_visible():
                close_btn.click()
            self.page.locator(selector).wait_for(state="hidden", timeout=5000)
        except Exception:
            pass
