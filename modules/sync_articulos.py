# modules/sync_articulos.py
from modules.base import BaseSincronizador
from utils.network import navegar_con_red, esperar_conexion_red

import pandas as pd
import tempfile
import os
import time

# ── URLs ──────────────────────────────────────────────────────────────────────
NODO_LOGIN_URL     = "https://nodo-practical.nodosolutions.com/"
NODO_PRODUCTOS_URL = "https://nodo-practical.nodosolutions.com/Producto/Index"

DIGIP_LOGIN_URL    = "https://app.digipwms.com/login"
DIGIP_HOME_URL     = "https://app.digipwms.com/home"
DIGIP_ARTICULOS_URL = (
    "https://app.digipwms.com/Configuracion/Articulo/ListadoArticulo?accion=consulta"
)

# ── Columnas del Excel de NODO ────────────────────────────────────────────────
NODO_COLUMNS = [
    'Id', 'Acciones', 'Imagen', 'SKU', 'CodigoBarra', 'Marca',
    'Descripcion', 'Categoria', 'UM', 'Embalaje', 'IVA',
    'CentroCosto', 'Servicio', 'Estado',
]

# ── Valores fijos para el formulario de DIGIP ─────────────────────────────────
DEFAULTS = {
    "rotacion":    "20",   # Media
    "dias_vida":   "730",
    "usa_lote":    True,
    "usa_venc":    True,
    "aprobado":    True,
    "activo_art":  True,
    "unidades":    "1",
    "alto":        "1",
    "ancho":       "1",
    "profundo":    "1",
    "peso":        "1",
    "um_id":       "1",    # Unidad
    "activo_ean":  True,
}

WAIT_MODAL_LOAD  = 800
WAIT_POST_ACTION = 500


class SincronizadorArticulos(BaseSincronizador):
    """
    Flujo completo de sincronización de artículos:
      (1) Login en NODO + descarga del Excel de productos.
      (2) Login en DIGIP + descarga del CSV de artículos existentes.
      (3) Cruce: detectar artículos de NODO ausentes en DIGIP
          (excluyendo los de marca 'sin nombre').
      (4) Carga secuencial en DIGIP vía modal 'Agregar Artículo Rápido'.
      (5) Limpieza de archivos temporales.
    """

    def _verificar_reset(self):
        """Lanza KeyboardInterrupt si se solicitó reinicio."""
        if self.reset_event and self.reset_event.is_set():
            raise KeyboardInterrupt("Reinicio forzado")

    def sincronizar(self, credenciales_dict):
        if not credenciales_dict:
            self.log("[ERROR] No se recibieron credenciales para el módulo de Artículos.")
            return

        nodo_user  = credenciales_dict.get('nodo_user')
        nodo_pass  = credenciales_dict.get('nodo_pass')
        digip_user = credenciales_dict.get('digip_user')
        digip_pass = credenciales_dict.get('digip_pass')

        temp_nodo  = None
        temp_digip = None

        self.log(f"\n{'='*50}")
        self.log("SINCRONIZACIÓN DE ARTICULOS")
        self.log(f"{'='*50}")

        try:
            # ── (1) Extracción NODO ──────────────────────────────────
            self._verificar_reset()
            self.verificar_pausa()
            temp_nodo = self._descargar_nodo(nodo_user, nodo_pass)
            if temp_nodo is None:
                self.log("[ARTICULOS] No se pudo obtener el Excel de NODO. Abortando.")
                return

            # ── (2) Extracción DIGIP ─────────────────────────────────
            self._verificar_reset()
            self.verificar_pausa()
            temp_digip = self._descargar_digip(digip_user, digip_pass)
            if temp_digip is None:
                self.log("[ARTICULOS] No se pudo obtener el CSV de DIGIP. Abortando.")
                return

            # ── (3) Cruce ────────────────────────────────────────────
            self._verificar_reset()
            self.verificar_pausa()
            df_faltantes = self._cruzar(temp_nodo, temp_digip)
            if df_faltantes is None or df_faltantes.empty:
                self.log("[ARTICULOS] No hay artículos nuevos para cargar.")
                return

            self.log(f"[ARTICULOS] {len(df_faltantes)} artículos a cargar en DIGIP.")

            # ── (4) Carga ────────────────────────────────────────────
            self._verificar_reset()
            self.verificar_pausa()
            self._cargar_en_digip(df_faltantes)

        finally:
            # ── (5) Limpieza ─────────────────────────────────────────
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

        self.log("[ARTICULOS] Navegando a listado de Productos NODO.")
        
        self._verificar_reset()
        self.verificar_pausa()
        
        if not navegar_con_red(self.page, NODO_PRODUCTOS_URL, self.log, self.stop_event, self.reset_event):
            return None

        self._verificar_reset()
        self.verificar_pausa()
        
        temp_path = os.path.join(tempfile.gettempdir(), f"nodo_productos_{int(time.time())}.xlsx")
        try:
            with self.page.expect_download(timeout=60000) as dl:
                self.page.click("button.buttons-excel")
            dl.value.save_as(temp_path)
            self.log(f"[ARTICULOS] Excel NODO descargado: {temp_path}")
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
        
        if not navegar_con_red(self.page, DIGIP_ARTICULOS_URL, self.log, self.stop_event, self.reset_event):
            return None

        self._verificar_reset()
        self.verificar_pausa()
        
        temp_path = os.path.join(tempfile.gettempdir(), f"digip_articulos_{int(time.time())}.csv")
        try:
            with self.page.expect_download(timeout=60000) as dl:
                self.page.click("button[name='accion'][value='descarga']")
            dl.value.save_as(temp_path)
            self.log(f"[ARTICULOS] CSV DIGIP descargado: {temp_path}")
            return temp_path
        except Exception as e:
            self.log(f"[ERROR] No se pudo descargar el CSV de DIGIP: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # CRUCE
    # ──────────────────────────────────────────────────────────────────────────

    def _cruzar(self, nodo_path: str, digip_path: str) -> pd.DataFrame | None:
        """Detecta los artículos de NODO que aún no existen en DIGIP."""
        self.log("[ARTICULOS] (3) Cruzando listas.")
        try:
            xlsx = pd.read_excel(nodo_path, header=1)
            xlsx.columns = NODO_COLUMNS

            csv = pd.read_csv(digip_path, encoding='latin-1', sep=None, engine='python')
            csv['Codigo'] = (
                csv['Codigo'].astype(str)
                .str.replace('.0', '', regex=False)
                .str.strip()
            )

            # Excluir artículos sin nombre real
            filtrado = xlsx[
                xlsx['Marca'].astype(str).str.strip().str.lower() != 'sin nombre'
            ].copy()
            filtrado['Id'] = filtrado['Id'].astype(str).str.strip()

            resultado = filtrado.merge(
                csv[['Codigo']],
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

            self.log(f"[ARTICULOS] Faltantes detectados: {len(faltantes)}")
            return faltantes

        except Exception as e:
            self.log(f"[ERROR] Error durante el cruce: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # CARGA EN DIGIP
    # ──────────────────────────────────────────────────────────────────────────

    def _cargar_en_digip(self, df: pd.DataFrame):
        """Carga secuencialmente cada artículo faltante en DIGIP."""
        self.log("[ARTICULOS] (4) Iniciando carga en DIGIP.")

        self._verificar_reset()
        if not navegar_con_red(self.page, DIGIP_ARTICULOS_URL, self.log, self.stop_event, self.reset_event):
            return

        ok_count   = 0
        skip_count = 0
        total      = len(df)

        for i, (_, row) in enumerate(df.iterrows()):
            # ── Puntos de control al inicio de cada iteración ────────
            self._verificar_reset()
            self.verificar_pausa()
            self._verificar_reset()  # Re-verificar tras salir de pausa

            codigo      = str(row.get('Id',          '') or '').strip()
            descripcion = str(row.get('Descripcion', '') or '').strip()
            cod_barra   = str(row.get('CodigoBarra', '') or '').strip() or codigo

            self.log(f"  [{i+1}/{total}] {codigo} - {descripcion}")

            if not codigo or not descripcion:
                self.log(f"    [WARN] Fila sin código o descripción. Se omite.")
                skip_count += 1
                continue

            try:
                self._abrir_modal()

                # Verificar reset tras la espera del modal (WAIT_MODAL_LOAD)
                self._verificar_reset()

                resultado = self._cargar_articulo(codigo, descripcion, cod_barra)
                if resultado == "ok":
                    ok_count += 1
                    self.log(f"    ✔ Guardado correctamente.")
                else:
                    skip_count += 1
                    self.log(f"    ~ Saltado (posiblemente ya existe).")
                self.page.wait_for_timeout(WAIT_POST_ACTION)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                self.log(f"    [ERROR] {e}")
                self._intentar_cerrar_modal()
                skip_count += 1

        self.log(f"\n[ARTICULOS] RESUMEN: {ok_count} cargados | {skip_count} saltados | {total} total.")

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS DE MODAL
    # ──────────────────────────────────────────────────────────────────────────

    def _abrir_modal(self):
        self.page.locator("button:has-text('Opciones')").click()
        item = self.page.locator("a.dropdown-item:has-text('Agregar Articulo Rapido')")
        item.wait_for(state="visible", timeout=5000)
        item.click()
        self.page.locator("#ModalInfo").wait_for(state="visible", timeout=10000)
        self.page.wait_for_timeout(WAIT_MODAL_LOAD)

    def _check_checkbox(self, checkbox_id: str, should_check: bool):
        """Marca o desmarca un checkbox clickeando su label envolvente."""
        cb = self.page.locator(f"#{checkbox_id}")
        is_checked = cb.is_checked()
        if (should_check and not is_checked) or (not should_check and is_checked):
            label = self.page.locator(f"label.checkbox-checked:has(#{checkbox_id})")
            label.click()

    def _cargar_articulo(self, codigo: str, descripcion: str, cod_barra: str) -> str:
        """Rellena el formulario y guarda. Retorna 'ok' o 'skip'."""
        p = self.page

        # ── Sección Artículo ───────────────────────────────────────────────
        p.fill("#Articulo_Descripcion",       descripcion)
        p.fill("#Articulo_CodigoArticulo",    codigo)
        p.select_option("#Articulo_ArticuloTipoRotacion", DEFAULTS["rotacion"])
        p.fill("#Articulo_DiasVidaUtil",      DEFAULTS["dias_vida"])

        self._check_checkbox("Articulo_UsaLote",        DEFAULTS["usa_lote"])
        self._check_checkbox("Articulo_UsaVencimiento", DEFAULTS["usa_venc"])
        self._check_checkbox("Articulo_Aprobado",       DEFAULTS["aprobado"])
        self._check_checkbox("Articulo_Activo",         DEFAULTS["activo_art"])

        # ── Sección EAN ────────────────────────────────────────────────────
        p.fill("#ArticuloUnidadMedidaEan_Unidades", DEFAULTS["unidades"])
        p.fill("#ArticuloUnidadMedidaEan_Alto",     DEFAULTS["alto"])
        p.fill("#ArticuloUnidadMedidaEan_Ancho",    DEFAULTS["ancho"])
        p.fill("#ArticuloUnidadMedidaEan_Profundo", DEFAULTS["profundo"])
        p.fill("#ArticuloUnidadMedidaEan_Peso",     DEFAULTS["peso"])
        p.fill("#ArticuloUnidadMedidaCodigoEan_Codigo", cod_barra)
        p.select_option("#ArticuloUnidadMedidaEan_UnidadMedida_Id", DEFAULTS["um_id"])

        self._check_checkbox("ArticuloUnidadMedidaEan_EsUnidadDeVenta", True)
        self._check_checkbox("ArticuloUnidadMedidaEan_EsUnidadMenor",   True)
        self._check_checkbox("ArticuloUnidadMedidaEan_Activo",          DEFAULTS["activo_ean"])

        # ── Guardar ────────────────────────────────────────────────────────
        p.locator("#btnab").click()

        try:
            p.locator("#ModalInfo").wait_for(state="hidden", timeout=5000)
            return "ok"
        except Exception:
            self._intentar_cerrar_modal()
            return "skip"

    def _intentar_cerrar_modal(self):
        try:
            close_btn = self.page.locator("#ModalInfo .close")
            if close_btn.is_visible():
                close_btn.click()
            self.page.locator("#ModalInfo").wait_for(state="hidden", timeout=5000)
        except Exception:
            pass
