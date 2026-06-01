# modules/sync_pedidos.py
from modules.base import BaseSincronizador
from utils.network import navegar_con_red, esperar_conexion_red
from utils.helpers import js_escape
import pandas as pd
import os
import time

# URLs de los sistemas
NODO_LOGIN_URL        = "https://nodo-practical.nodosolutions.com/"
NODO_LIBRO_VENTA_URL  = "https://nodo-practical.nodosolutions.com/LibroVenta/index"
DIGIP_LOGIN_URL       = "https://app.digipwms.com/login"
DIGIP_HOME_URL        = "https://app.digipwms.com/home"
DIGIP_PEDIDOS_URL     = "https://app.digipwms.com/Preparacion/Pedido"

# Parámetros operativos
TIMEOUT_ARTICULO      = 15000
TIMEOUT_SWEETALERT    = 5000
WAIT_MODAL_LOAD       = 800
WAIT_POST_ACTION      = 500

# Columnas aceptadas para el importe (en orden de prioridad)
COLUMNAS_IMPORTE      = ['Total', 'Importe', 'Monto', 'Valor']

# Valor del option "Activo" en el select ContenedorEstado_Id
# Se resuelve dinámicamente en tiempo de ejecución; este es el fallback
CONTENEDOR_ACTIVO_LABEL = "Activo"

# Selector JS para contar solo filas reales del servidor
# (Pedido_Id con valor numérico distinto de 0; la fila del form siempre tiene value="0")
JS_CONTAR_FILAS = (
    "() => document.querySelectorAll("
    "'#ListadoPedidoDetalle tbody tr "
    "input[name$=\"Pedido_Id\"][value]:not([value=\"0\"])')"
    ".length"
)


class SincronizadorPedidos(BaseSincronizador):
    """
    Módulo especialista de Pedidos. Ciclo ETL completo:
      (1ro) Visitar Libro de Ventas y aplicar filtros (Conceptos 6 y 3, Consolidado NO).
      (2do) Descarga del Excel.
      (3ro) Agrupación por Factura.
      (4to) Carga secuencial en DIGIP WMS.

    Garantías adicionales:
      - Registro de facturas fallidas al finalizar.
      - No carga facturas con datos de cabecera incompletos.
      - Pausa/reanudación respetada también dentro de la carga de artículos.
      - Limpieza del archivo temporal inmediatamente tras leerlo.
    """

    def _verificar_reset(self):
        """Lanza KeyboardInterrupt si se solicitó reinicio."""
        if self.reset_event and self.reset_event.is_set():
            raise KeyboardInterrupt("Reinicio forzado")

    def sincronizar(self, credenciales_dict):
        """Punto de entrada obligatorio que ejecuta los 5 pasos del flujo."""
        if not credenciales_dict:
            self.log("[ERROR] No se recibieron credenciales para el módulo de Pedidos.")
            return

        nodo_user  = credenciales_dict.get('nodo_user')
        nodo_pass  = credenciales_dict.get('nodo_pass')
        digip_user = credenciales_dict.get('digip_user')
        digip_pass = credenciales_dict.get('digip_pass')
        
        self.log(f"\n{'='*50}")
        self.log("SINCRONIZACIÓN DE PEDIDOS")
        self.log(f"{'='*50}")

        # === PASOS (1 Y 2): EXTRACCIÓN ===
        self._verificar_reset()
        self.verificar_pausa()
        df_nodo = self._extraer_reporte_nodo(nodo_user, nodo_pass)
        if df_nodo is None or df_nodo.empty:
            self.log("[PEDIDOS] El informe de NODO está vacío o no se pudo descargar. Abortando.")
            return

        # === PASO (4): FILTRADO ===
        self.log("[PEDIDOS] Agrupando líneas del informe por 'Factura'.")
        df_nodo.columns = df_nodo.columns.str.strip()
        df_nodo = df_nodo.dropna(subset=['Factura'])

        # Invertir el orden del DataFrame para procesar desde la factura
        # más reciente (última fila del Excel) hacia la más antigua
        df_nodo = df_nodo.iloc[::-1].reset_index(drop=True)

        # sort=False preserva el orden de aparición tras la inversión
        # en lugar de reordenar las claves alfabéticamente
        pedidos_agrupados = df_nodo.groupby('Factura', sort=False)

        # === PASO (5): CARGA ===
        self._verificar_reset()
        self.verificar_pausa()
        self._procesar_carga_digip(pedidos_agrupados, digip_user, digip_pass)

    # ──────────────────────────────────────────────────────────────
    # EXTRACCIÓN
    # ──────────────────────────────────────────────────────────────

    def _extraer_reporte_nodo(self, user, password):
        
        self._verificar_reset()
        self.verificar_pausa()

        self.log("[PEDIDOS] Aplicando filtros en el Libro de Ventas en NODO.")
        self._verificar_reset()
        self.verificar_pausa()
        if not navegar_con_red(self.page, NODO_LIBRO_VENTA_URL, self.log, self.stop_event, self.reset_event):
            return None

        self.page.select_option("#cboConcepto", ["6", "3"])
        self.page.evaluate("$('#cboConcepto').trigger('change')")
        self.page.select_option("#cboConsolidado", "0")
        self.page.wait_for_selector("#btnBuscar", state="visible", timeout=15000)
        self.page.click("#btnBuscar")
        self.page.wait_for_load_state("networkidle")

        self.log("[PEDIDOS] Descargando el informe de NODO.")
        self._verificar_reset()
        self.verificar_pausa()
        temp_path = None
        try:
            import tempfile
            temp_dir  = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"nodo_ventas_{int(time.time())}.xlsx")

            with self.page.expect_download(timeout=60000) as dl:
                self.page.click("#btnDownloadExcel")
            dl.value.save_as(temp_path)

            # Leer y liberar el archivo inmediatamente (evita acumulación de atexit)
            try:
                df = pd.read_excel(temp_path, sheet_name='InformeLibroVenta')
            except Exception:
                df = pd.read_excel(temp_path, header=0)

            return df

        except Exception as e:
            self.log(f"[ERROR] Error durante la extracción desde NODO: {e}")
            return None
        finally:
            # Limpieza inmediata en lugar de diferirla con atexit
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    # ──────────────────────────────────────────────────────────────
    # CARGA EN DIGIP
    # ──────────────────────────────────────────────────────────────

    def _procesar_carga_digip(self, pedidos_agrupados, user, password):
        self._verificar_reset()
        self.verificar_pausa()

        total          = len(pedidos_agrupados)
        fallidas       = []
        saltadas       = 0
        cargadas       = 0
        skips_seguidos = 0
        MAX_SKIPS      = 50

        self.log(f"\n[PEDIDOS] {total} documentos a evaluar.")

        for factura, info_grupo in pedidos_agrupados:
            self._verificar_reset()
            self.verificar_pausa()
            self._verificar_reset()  # Re-verificar tras salir de pausa
            self.log(f"\n→ Evaluando Factura N°: {factura}")

            # ── Verificar existencia ────────────────────────────────
            check_url = f"{DIGIP_PEDIDOS_URL}?Codigo={factura}&PedidoEstado="
            if not navegar_con_red(self.page, check_url, self.log, self.stop_event, self.reset_event):
                self.log(f"  [WARN] No se pudo navegar para verificar {factura}. Se omite.")
                fallidas.append((factura, "Error de navegación en verificación"))
                skips_seguidos = 0  # Un error no es un SKIP; reiniciar contador
                continue

            # Esperar al primer selector relevante:
            #   • div.alert-blue  → "No se encontraron registros" (hay que cargar)
            #   • tbody tr        → la factura ya existe (saltar)
            try:
                self.page.wait_for_selector(
                    "div.alert-blue, #ListadoPedidoDetalle tbody tr, table tbody tr",
                    timeout=8000
                )
            except Exception:
                pass  # Si ninguno aparece, continuar y evaluar con count()

            # div.alert-blue presente → "No se encontraron registros" → hay que cargar
            # div.alert-blue ausente  → la factura ya existe → saltar
            try:
                alert_count = self.page.locator("div.alert-blue").count()
            except Exception:
                alert_count = 0

            if alert_count == 0:
                self.log(f"  [SKIP] Factura {factura} ya existe en Digip.")
                saltadas       += 1
                skips_seguidos += 1

                if skips_seguidos >= MAX_SKIPS:
                    self.log(
                        f"\n[PEDIDOS] {MAX_SKIPS} SKIPs consecutivos detectados. "
                        f"Todo lo pendiente ya está sincronizado. Finalizando anticipadamente."
                    )
                    break

                continue

            # Si llegamos aquí hay que cargar → reiniciar el contador
            skips_seguidos = 0

            # ── Validar datos mínimos antes de intentar la carga ───
            primera_fila = info_grupo.iloc[0]
            cliente  = str(primera_fila.get('Cliente', '')).strip()
            id_agrup = str(primera_fila.get('IdAgrupador', '')).strip()

            if not cliente:
                self.log(f"  [ERROR] Factura {factura} no tiene cliente. Se omite.")
                fallidas.append((factura, "Cliente vacío"))
                continue

            col_importe = next((c for c in COLUMNAS_IMPORTE if c in info_grupo.columns), None)
            if col_importe is None:
                self.log(f"  [ERROR] Factura {factura}: no se encontró columna de importe {COLUMNAS_IMPORTE}. Se omite.")
                fallidas.append((factura, "Sin columna de importe"))
                continue

            # ── Cargar ─────────────────────────────────────────────
            self.log(f"  [OK] Factura {factura} no encontrada. Procediendo.")
            exito = self._inyectar_pedido_modal(factura, info_grupo, col_importe)
            if exito:
                cargadas += 1
            else:
                fallidas.append((factura, "Error durante la inyección"))

        # ── Resumen final ───────────────────────────────────────────
        self.log(f"\n{'─'*50}")
        self.log(f"[PEDIDOS] RESUMEN: {cargadas} cargadas | {saltadas} ya existían | {len(fallidas)} fallidas de {total} totales.")
        if fallidas:
            self.log("[PEDIDOS] Facturas con error:")
            for f, motivo in fallidas:
                self.log(f"  ✘ {f} → {motivo}")
        self.log(f"{'─'*50}")

    # ──────────────────────────────────────────────────────────────
    # INYECCIÓN DEL MODAL
    # ──────────────────────────────────────────────────────────────

    def _inyectar_pedido_modal(self, factura, info_grupo, col_importe):
        """
        Abre el modal de nuevo pedido, carga la cabecera y todos los ítems.
        Retorna True si completó correctamente, False si hubo algún error.
        """
        try:
            if not navegar_con_red(self.page, DIGIP_PEDIDOS_URL, self.log, self.stop_event, self.reset_event):
                return False

            # ── Abrir modal ─────────────────────────────────────────
            self.page.click("button:has-text('Opciones')")
            self.page.click("a.dropdown-item:has-text('Nuevo Pedido')")
            self.page.wait_for_selector("#Codigo", state="visible", timeout=15000)
            self.page.wait_for_timeout(WAIT_MODAL_LOAD)

            # Verificar reset tras la espera del modal
            self._verificar_reset()

            # Asegurar interactividad del modal (puede tener aria-hidden)
            self.page.evaluate("""
                var m = document.getElementById('ModalInfo');
                if (m) {
                    m.removeAttribute('aria-hidden');
                    m.style.pointerEvents = 'auto';
                }
            """)

            primera_fila = info_grupo.iloc[0]
            cliente  = str(primera_fila.get('Cliente', '')).strip()
            vendedor = str(primera_fila.get('Vendedor', '')).strip()
            id_agrup = str(primera_fila.get('IdAgrupador', '')).strip()
            factura_esc = js_escape(str(factura))

            # ── Detectar el id real del <form> ───────────────────────
            form_id = self.page.evaluate("""
                () => {
                    var f = document.querySelector('#ModalInformacion form');
                    return f ? f.id : 'form0';
                }
            """) or 'form0'

            # ── 1. Código ───────────────────────────────────────────
            self.page.evaluate(f"""
                var el = document.querySelector('#{form_id} #Codigo');
                if (!el) el = document.getElementById('Codigo');
                if (el) {{
                    el.value = '{factura_esc}';
                    el.dispatchEvent(new Event('input',  {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
            """)

            # ── 2. Ubicación Cliente (select2) ──────────────────────
            try:
                self.page.click("#selectCliente span.select2-selection")
                search_input = self.page.wait_for_selector(
                    "input.select2-search__field", state="visible", timeout=8000
                )
                search_input.focus()
                self.page.fill("input.select2-search__field", cliente)
                self.page.wait_for_selector(
                    "ul#select2-ClienteUbicacion_Id-results "
                    "li.select2-results__option:not(.select2-results__message)",
                    timeout=10000
                )
                self.page.click(
                    "ul#select2-ClienteUbicacion_Id-results "
                    "li.select2-results__option:first-child"
                )
                self.page.wait_for_timeout(WAIT_POST_ACTION)

                valor_asignado = self.page.evaluate(
                    "() => document.getElementById('ClienteUbicacion_Id')?.value || ''"
                )
                if not valor_asignado or not valor_asignado.strip().lstrip('-').isdigit():
                    raise ValueError(
                        f"Select2 no asignó ningún valor al campo ClienteUbicacion_Id "
                        f"(value='{valor_asignado}'). El cliente '{cliente}' no fue encontrado."
                    )

                self.log(f"  → Cliente seleccionado: {cliente} (id={valor_asignado})")

            except Exception as e:
                self.log(f"  [ERROR] No se pudo seleccionar el cliente '{cliente}': {e}")
                return False

            # ── 3. Estado Contenedor: seleccionar "Activo" por label ─
            try:
                self.page.select_option(
                    "#ContenedorEstado_Id", label=CONTENEDOR_ACTIVO_LABEL
                )
            except Exception:
                self.page.evaluate("""
                    var sel = document.getElementById('ContenedorEstado_Id');
                    if (sel) {
                        for (var i = 0; i < sel.options.length; i++) {
                            if (sel.options[i].value !== '') {
                                sel.value = sel.options[i].value;
                                sel.dispatchEvent(new Event('change', {bubbles: true}));
                                break;
                            }
                        }
                    }
                """)

            # ── 4. Importe ──────────────────────────────────────────
            total_factura = info_grupo[col_importe].sum()
            self.page.fill("#Importe", str(int(total_factura)))

            # ── 5. Orden (IdAgrupador) ──────────────────────────────
            if id_agrup:
                self.page.fill("#OrdenPreparacion", id_agrup)

            # ── 6. Código Despacho ──────────────────────────────────
            self.page.evaluate(f"""
                var el = document.querySelector('#{form_id} #CodigoDespacho');
                if (!el) el = document.getElementById('CodigoDespacho');
                if (el) {{
                    el.value = '{factura_esc}';
                    el.dispatchEvent(new Event('input',  {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}
            """)

            # ── 7. Código de Envío ──────────────────────────────────
            self.page.fill("#CodigoDeEnvio", str(factura))

            # ── 8. Tipo de Envío (Propio) ───────────────────────────
            self.page.select_option("#ServicioDeEnvioTipo", value="1")

            # ── 9. Observación ──────────────────────────────────────
            if vendedor:
                self.page.fill("#Observacion", f"Vendedor {vendedor}")

            self.log(f"  [DIGIP] Cabecera cargada para Factura {factura}.")

            # ── Ítems ───────────────────────────────────────────────
            self.log("  → Cargando artículos.")
            articulos_ok   = 0
            articulos_fail = 0

            for _, fila in info_grupo.iterrows():
                self._verificar_reset()
                self.verificar_pausa()
                self._verificar_reset()

                # Parseo seguro de IdProducto
                raw_id = fila.get('IdProducto')
                if pd.isna(raw_id):
                    self.log(f"    [WARN] Fila con IdProducto vacío. Se omite.")
                    articulos_fail += 1
                    continue
                try:
                    id_producto = str(int(float(raw_id)))
                except (ValueError, TypeError) as e:
                    self.log(f"    [WARN] IdProducto inválido '{raw_id}': {e}. Se omite.")
                    articulos_fail += 1
                    continue

                # Parseo seguro de Cantidad
                raw_cant = fila.get('Cantidad', 1)
                try:
                    cantidad = int(float(raw_cant))
                    if cantidad <= 0:
                        raise ValueError("Cantidad debe ser positiva")
                except (ValueError, TypeError) as e:
                    self.log(f"    [WARN] Cantidad inválida '{raw_cant}' para {id_producto}: {e}. Se omite.")
                    articulos_fail += 1
                    continue

                self.log(f"    → Artículo: {id_producto} | Cantidad: {cantidad}")
                if self._agregar_articulo(id_producto, cantidad):
                    articulos_ok += 1
                else:
                    articulos_fail += 1
                    self.log(f"    [WARN] Artículo {id_producto} no se pudo cargar.")

            self.log(f"  → Ítems: {articulos_ok} cargados, {articulos_fail} fallidos.")

            # ── Cerrar modal ────────────────────────────────────────
            try:
                self.page.click("button.btn.btn-secondary[data-dismiss='modal']")
                self.page.wait_for_timeout(WAIT_POST_ACTION)
            except Exception:
                pass

            # ── SweetAlert2 ─────────────────────────────────────────
            self._manejar_sweetalert(factura)

            self.log(f"  [DIGIP] Todos los ítems cargados para Factura {factura}.")
            return True

        except KeyboardInterrupt:
            raise
        except Exception as e:
            self.log(f"  [ERROR] Falla al inyectar la factura {factura}: {e}")
            return False

    # ──────────────────────────────────────────────────────────────
    # SWEETALERT2
    # ──────────────────────────────────────────────────────────────

    def _manejar_sweetalert(self, factura):
        """Lee y confirma el popup SweetAlert2 si aparece."""
        try:
            self.page.wait_for_selector(
                ".swal2-popup.swal2-show", state="visible", timeout=TIMEOUT_SWEETALERT
            )
            swal_title   = self.page.locator("#swal2-title").inner_text()
            swal_content = self.page.locator("#swal2-content").inner_text()

            iconos = {
                "swal2-error":    "❌ ERROR",
                "swal2-success":  "✅ ÉXITO",
                "swal2-warning":  "⚠️ ADVERTENCIA",
                "swal2-info":     "ℹ️ INFO",
                "swal2-question": "❓ PREGUNTA",
            }
            tipo = "📢 NOTIFICACIÓN"
            for clase, etiqueta in iconos.items():
                icono_el = self.page.locator(f".swal2-icon.{clase}")
                if icono_el.count() > 0 and icono_el.is_visible():
                    tipo = etiqueta
                    break

            self.log(f"  [SWAL2] {tipo} | {swal_title} → {swal_content}")
            self.page.click("button.swal2-confirm")
            self.page.wait_for_selector(".swal2-popup", state="hidden", timeout=TIMEOUT_SWEETALERT)
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────
    # ARTÍCULOS
    # ──────────────────────────────────────────────────────────────

    def _agregar_articulo(self, id_producto, cantidad):
        MAX_INTENTOS = 2

        for intento in range(1, MAX_INTENTOS + 1):
            try:
                # ── Esperar que el modal esté listo ─────────────────────
                self.page.wait_for_selector(
                    "#selectArticuloUnidades span.select2-selection",
                    state="visible",
                    timeout=15000
                )

                # ── Seleccionar artículo via Select2 ────────────────────
                self.page.click("#selectArticuloUnidades span.select2-selection")
                search = self.page.wait_for_selector(
                    "input.select2-search__field", state="visible", timeout=10000
                )
                search.focus()
                self.page.fill("input.select2-search__field", id_producto)

                try:
                    self.page.wait_for_selector(
                        "ul#select2-Articulo_Id-results "
                        "li.select2-results__option:not(.select2-results__message)",
                        timeout=TIMEOUT_ARTICULO
                    )
                except Exception:
                    self.log(f"    [WARN] Artículo {id_producto} no encontrado en Select2. Se omite.")
                    try:
                        self.page.keyboard.press("Escape")
                    except Exception:
                        pass
                    return False

                self.page.click(
                    "ul#select2-Articulo_Id-results li.select2-results__option:first-child"
                )

                # ── Cantidad ────────────────────────────────────────────
                self.page.wait_for_selector("#Unidades", state="visible", timeout=5000)
                self.page.fill("#Unidades", str(cantidad))

                # ── Guardar ─────────────────────────────────────────────
                # Contamos solo filas "reales": aquellas cuyo input hidden
                # Pedido_Id tiene un valor numérico > 0.
                # La fila del formulario de entrada siempre tiene value="0"
                # y queda excluida, evitando el falso +1 del conteo anterior.
                filas_antes = self.page.evaluate(JS_CONTAR_FILAS)
                self.page.click("#btnab")

                # ── Confirmar inserción por conteo de filas reales ──────
                try:
                    self.page.wait_for_function(
                        f"() => document.querySelectorAll("
                        f"'#ListadoPedidoDetalle tbody tr "
                        f"input[name$=\"Pedido_Id\"][value]:not([value=\"0\"])')"
                        f".length > {filas_antes}",
                        timeout=10000,
                        polling=150
                    )
                    filas_despues = self.page.evaluate(JS_CONTAR_FILAS)
                    self.log(
                        f"      ✔ Artículo {id_producto} confirmado "
                        f"({filas_despues} ítems)."
                    )
                    try:
                        self.page.wait_for_function(
                            "() => {"
                            "  const u = document.getElementById('Unidades');"
                            "  return u && u.offsetParent !== null && u.value === '';"
                            "}",
                            timeout=8000
                        )
                    except Exception:
                        pass
                    return True

                except Exception:
                    filas_despues = self.page.evaluate(JS_CONTAR_FILAS)
                    self.log(
                        f"      [WARN] Artículo {id_producto} rechazado por el servidor "
                        f"(filas antes={filas_antes}, después={filas_despues}). Se omite."
                    )
                    try:
                        self.page.wait_for_function(
                            "() => {"
                            "  const u = document.getElementById('Unidades');"
                            "  return u && u.offsetParent !== null && u.value === '';"
                            "}",
                            timeout=8000
                        )
                    except Exception:
                        pass
                    return False

            except KeyboardInterrupt:
                raise

            except Exception as e:
                err = str(e)

                # ── Sin conexión: esperar y reintentar ──────────────────
                if "ERR_INTERNET_DISCONNECTED" in err or "net::ERR_" in err:
                    if not esperar_conexion_red(
                        self.log, self.stop_event, self.reset_event
                    ):
                        return False
                    try:
                        self.page.wait_for_selector(
                            "#selectArticuloUnidades span.select2-selection",
                            state="visible", timeout=20000
                        )
                    except Exception:
                        self.log(
                            f"    [ERROR] Modal no recuperado tras reconexión "
                            f"para {id_producto}. Se omite."
                        )
                        return False
                    continue

                # ── Timeout u otro error transitorio: reintentar una vez ─
                if intento < MAX_INTENTOS:
                    self.log(
                        f"    [WARN] Error en intento {intento} para {id_producto}: "
                        f"{err[:120]}. Reintentando."
                    )
                    try:
                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(500)
                    except Exception:
                        pass
                    continue

                # ── Agotados los intentos ───────────────────────────────
                self.log(
                    f"    [ERROR] Artículo {id_producto} descartado tras "
                    f"{MAX_INTENTOS} intentos: {err[:200]}"
                )
                return False

        return False  # fallback de seguridad
