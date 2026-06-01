import customtkinter as ctk
import tkinter as tk
import queue
import re
import asyncio
import threading
import io
import numpy as np
import sounddevice as sd
import edge_tts
import miniaudio
import pandas as pd
from worker import SyncWorker
from utils.credentials import guardar_credenciales, credenciales_configuradas
import sys
import os

def resource_path(filename):
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)

# ── Tema y Paleta de Colores ──────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLOR_BG             = "#0e0e1a"
COLOR_PANEL          = "#13132b"
COLOR_ACCENT         = "#1a1a40"
COLOR_BORDER         = "#2a2a55"
COLOR_BTN_BLUE       = "#1a56db"
COLOR_BTN_HOVER      = "#1e6ef5"
COLOR_BTN_STOP       = "#c0392b"
COLOR_BTN_STOP_HOVER = "#e74c3c"
COLOR_BTN_RESET      = "#2c3e50"
COLOR_BTN_CONFIG     = "#2d4a22"
COLOR_BTN_CONFIG_HOV = "#3a6b2a"
COLOR_TEXT           = "#e8eaf6"
COLOR_TEXT_DIM       = "#8892a4"
COLOR_CONSOLE        = "#080810"
COLOR_STATUS_OK      = "#00e676"
COLOR_STATUS_RUN     = "#ffd600"

FONT_APP_TITLE  = ("Segoe UI", 15, "bold")
FONT_SECTION    = ("Segoe UI", 10, "bold")
FONT_LABEL      = ("Segoe UI", 11)
FONT_VALUE_LG   = ("Segoe UI", 26, "bold")
FONT_VALUE_MD   = ("Segoe UI", 13, "bold")
FONT_BTN        = ("Segoe UI", 11, "bold")
FONT_CONSOLE    = ("Consolas", 11)
FONT_FOOTER     = ("Segoe UI", 10)

CONSOLE_FONT_MIN     = 8
CONSOLE_FONT_MAX     = 22
CONSOLE_FONT_DEFAULT = 11
POLL_INTERVAL_MS = 200

# ── Configuración de Audio (voz.py integrada) ─────────────────────────────────
SR = 44100
VOZ_TOMAS = "es-AR-TomasNeural"

def alerta_sonora():
    def bell(freq, dur=0.6, vol=0.45):
        t = np.linspace(0, dur, int(SR * dur), False)
        env = np.exp(-4 * t / dur)
        return vol * env * (np.sin(2*np.pi*freq*t) + 0.3*np.sin(2*np.pi*freq*2*t))
    wave = np.concatenate([bell(880, 0.5), np.zeros(int(SR*0.08)), bell(1318, 0.7)])
    sd.play(wave.astype(np.float32), SR)
    sd.wait()

async def descargar_y_reproducir_tts(texto):
    try:
        communicate = edge_tts.Communicate(texto, VOZ_TOMAS)
        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        buffer.seek(0)
        decoded = miniaudio.decode(buffer.read(), output_format=miniaudio.SampleFormat.SIGNED16)
        samples = np.frombuffer(decoded.samples, dtype=np.int16).astype(np.float32) / 2**15
        if decoded.nchannels == 2:
            samples = samples.reshape((-1, 2))
        sd.play(samples, decoded.sample_rate)
        sd.wait()
    except Exception as e:
        print(f"Error en TTS: {e}")

def ejecutar_en_hilo(func, *args):
    threading.Thread(target=func, args=args, daemon=True).start()

def ejecutar_async_en_hilo(texto):
    def run():
        asyncio.run(descargar_y_reproducir_tts(texto))
    threading.Thread(target=run, daemon=True).start()


# ══════════════════════════════════════════════════════════════════════════════
# VENTANA DE CONFIGURACIÓN DE CREDENCIALES (SOLO NODO)
# ══════════════════════════════════════════════════════════════════════════════

class VentanaCredenciales(ctk.CTkToplevel):
    def __init__(self, parent, on_guardado=None):
        super().__init__(parent)
        self.title("Configurar Credenciales NODO")
        self.geometry("440x320")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_PANEL)
        self.on_guardado = on_guardado
        try:
            self.after(200, lambda: self.iconbitmap(resource_path("icono.ico")))
        except Exception:
            pass
        self.after(20, self._build)

    def _campo_password(self, parent, atributo: str, placeholder: str, pady_bottom: int):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(padx=28, pady=(0, pady_bottom), fill="x")

        entry = ctk.CTkEntry(row, width=344, show="●", placeholder_text=placeholder)
        entry.pack(side="left")
        setattr(self, atributo, entry)

        visible_var = {"v": False}

        def toggle():
            visible_var["v"] = not visible_var["v"]
            entry.configure(show="" if visible_var["v"] else "●")
            btn.configure(text="🙈" if visible_var["v"] else "👁")

        btn = ctk.CTkButton(
            row, text="👁", width=34, height=34,
            font=("Segoe UI", 14),
            fg_color=COLOR_ACCENT, hover_color=COLOR_BORDER,
            corner_radius=6, command=toggle
        )
        btn.pack(side="left", padx=(6, 0))

    def _build(self):
        f = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=0)
        f.pack(fill="both", expand=True)

        ctk.CTkLabel(
            f, text="Configurar Credenciales NODO",
            font=FONT_APP_TITLE, text_color=COLOR_TEXT
        ).pack(padx=28, pady=(22, 4), anchor="w")

        ctk.CTkLabel(
            f,
            text="Los datos se guardan cifrados en el sistema operativo.",
            font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM, justify="left"
        ).pack(padx=28, pady=(0, 16), anchor="w")

        ctk.CTkLabel(f, text="NODO — Usuario (email)",
                     font=FONT_SECTION, text_color=COLOR_TEXT_DIM
                     ).pack(padx=28, pady=(0, 2), anchor="w")
        self.entry_nodo_user = ctk.CTkEntry(f, width=384, placeholder_text="usuario@ejemplo.com")
        self.entry_nodo_user.pack(padx=28, pady=(0, 10))

        ctk.CTkLabel(f, text="NODO — Contraseña",
                     font=FONT_SECTION, text_color=COLOR_TEXT_DIM
                     ).pack(padx=28, pady=(0, 2), anchor="w")
        self._campo_password(f, "entry_nodo_pass", "••••••••", pady_bottom=18)

        self.lbl_error = ctk.CTkLabel(f, text="", font=("Segoe UI", 10), text_color="#f56565")
        self.lbl_error.pack(padx=28, pady=(0, 4))

        ctk.CTkButton(
            f, text="🔒  Guardar de forma segura",
            font=FONT_BTN, fg_color=COLOR_BTN_CONFIG, hover_color=COLOR_BTN_CONFIG_HOV,
            corner_radius=7, height=40, command=self._guardar
        ).pack(fill="x", padx=28, pady=(0, 18))

        self.update_idletasks()
        self.focus_force()
        self.grab_set()
        self.lift()

    def _guardar(self):
        nu = self.entry_nodo_user.get().strip()
        np = self.entry_nodo_pass.get().strip()

        if not all([nu, np]):
            self.lbl_error.configure(text="Todos los campos son obligatorios.")
            return

        ok = guardar_credenciales(nu, np)
        if ok:
            if self.on_guardado:
                self.on_guardado()
            self.destroy()
        else:
            self.lbl_error.configure(text="Error al guardar. Verifica permisos del sistema.")


# ── Componente CTkTable para Listado de Pedidos ───────────────────────────────
class CTkTable(ctk.CTkFrame):
    def __init__(self, parent, headers, col_weights, **kwargs):
        super().__init__(parent, fg_color=COLOR_BORDER, corner_radius=8,
                         border_width=1, border_color=COLOR_BORDER, **kwargs)
        self.headers = headers
        self.col_weights = col_weights

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Cabecera ──────────────────────────────────────────────────────────
        self.header_frame = ctk.CTkFrame(self, fg_color=COLOR_PANEL,
                                         corner_radius=0, height=45)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_propagate(False)

        for col_idx, weight in enumerate(col_weights):
            self.header_frame.grid_columnconfigure(col_idx, weight=weight)

        self.header_labels = []
        for col_idx, header in enumerate(headers):
            label = ctk.CTkLabel(
                self.header_frame,
                text=header,
                font=("Segoe UI", 11, "bold"),
                text_color=COLOR_TEXT,
                fg_color=COLOR_PANEL,
                anchor="center",
                height=45,
            )
            label.grid(row=0, column=col_idx, sticky="nsew",
                       padx=(0 if col_idx == 0 else 1, 0))
            self.header_labels.append(label)

        # ── Body desplazable ──────────────────────────────────────────────────
        # CTkScrollableFrame solo expone 1 columna (col 0) hacia sus hijos;
        # las filas deben ocupar esa única columna y manejar internamente
        # sus propias columnas mediante un Frame hijo con grid.
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0
        )
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        # El ScrollableFrame solo tiene una columna real que debe expandirse
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        self.rows = []

    # ------------------------------------------------------------------
    def _get_inner_frame(self):
        """Devuelve el frame interno real del CTkScrollableFrame."""
        # customtkinter expone el canvas como _parent_canvas
        # y el frame contenedor como _scrollable_frame (v5.x) o como el
        # primer hijo del canvas.  Usamos el atributo público cuando existe.
        if hasattr(self.scroll_frame, "_scrollable_frame"):
            return self.scroll_frame._scrollable_frame
        # Fallback seguro: iterar hijos del canvas
        for child in self.scroll_frame.winfo_children():
            return child
        return self.scroll_frame

    # ------------------------------------------------------------------
    def clear(self):
        """Elimina todas las filas de la tabla."""
        for row_frame, _labels in self.rows:
            row_frame.destroy()
        self.rows.clear()
        self.update_idletasks()

    # ------------------------------------------------------------------
    def add_row(self, row_data):
        """Agrega una fila a la tabla."""
        row_idx = len(self.rows)

        # El row_frame va dentro del CTkScrollableFrame (col 0) y se
        # extiende todo el ancho; NO usamos grid_propagate(False) porque
        # eso impide que el frame crezca con el ancho del contenedor.
        row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        row_frame.grid(row=row_idx, column=0, sticky="ew", pady=(0, 1))

        # Configurar las columnas internas del row_frame
        for col_idx, weight in enumerate(self.col_weights):
            row_frame.grid_columnconfigure(col_idx, weight=weight)

        row_labels = []

        for col_idx, text in enumerate(row_data):
            text_color = COLOR_TEXT
            if col_idx == 4:  # Columna Estado
                val_lower = text.lower()
                if "finiquitado" in val_lower or "completado" in val_lower:
                    text_color = COLOR_STATUS_OK
                elif "pendiente" in val_lower:
                    text_color = COLOR_STATUS_RUN
                elif "anulado" in val_lower or "cancelado" in val_lower:
                    text_color = COLOR_BTN_STOP_HOVER

            label = ctk.CTkLabel(
                row_frame,
                text=text,
                font=("Segoe UI", 11),
                text_color=text_color,
                fg_color=COLOR_CONSOLE,
                anchor="center" if col_idx in [0, 3, 4] else "w",
                height=38,
            )
            label.grid(
                row=0,
                column=col_idx,
                sticky="nsew",
                padx=(0 if col_idx == 0 else 1, 0),
                pady=0,
            )
            row_labels.append(label)

        self.rows.append((row_frame, row_labels))

        # Scroll al final para ver los elementos nuevos
        try:
            self.scroll_frame._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# VENTANA PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PRACTICAL PEDIDOS")
        try:
            self.iconbitmap(resource_path("icono.ico"))
        except Exception:
            pass

        self.geometry("960x620")
        self.minsize(760, 480)
        self.configure(fg_color=COLOR_BG)

        self.worker = SyncWorker()
        self._factura_count = 0

        self._build_ui()
        self._poll_queue()
        self._verificar_credenciales_al_inicio()
        
        # Cargar datos después de que la UI esté completamente renderizada
        self.after(100, self.cargar_datos_excel)

    def _verificar_credenciales_al_inicio(self):
        if not credenciales_configuradas():
            self._log_console("[WARN] No se encontraron credenciales. Configúralas antes de iniciar.", "warn")
            self.lbl_footer.configure(text="⚠ Credenciales no configuradas.")

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_panel_izquierdo()
        self._build_panel_derecho()

    def _build_panel_izquierdo(self):
        left = ctk.CTkFrame(self, width=256, fg_color=COLOR_PANEL, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)

        # ── Cabecera ────────────────────────────────────────────
        ctk.CTkLabel(
            left, text="P E D I D O S",
            font=FONT_APP_TITLE, text_color=COLOR_TEXT
        ).pack(padx=18, pady=(22, 2), anchor="w")

        ctk.CTkLabel(
            left, text="Alerta de nuevos pedidos en NODO",
            font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM
        ).pack(padx=18, pady=(0, 24), anchor="w")

        # ── Checkboxes ──────────────────────────────────────────
        self.check_sonido_var = ctk.StringVar(value="off")
        self.check_sonido = ctk.CTkCheckBox(
            left, text="Sonido de notification.",
            font=FONT_LABEL, text_color=COLOR_TEXT,
            variable=self.check_sonido_var, onvalue="on", offvalue="off",
            command=self._on_check_sonido
        )
        self.check_sonido.pack(padx=18, pady=(0, 16), anchor="w")

        self.check_lectura_var = ctk.StringVar(value="off")
        self.check_lectura = ctk.CTkCheckBox(
            left, text="Lectura de mensajes.",
            font=FONT_LABEL, text_color=COLOR_TEXT,
            variable=self.check_lectura_var, onvalue="on", offvalue="off",
            command=self._on_check_lectura
        )
        self.check_lectura.pack(padx=18, pady=(0, 24), anchor="w")

        # ── Botones de Control ──────────────────────────────────
        self.btn_iniciar = ctk.CTkButton(
            left, text="▶  Iniciar Sincronización",
            font=FONT_BTN, fg_color=COLOR_BTN_BLUE, hover_color=COLOR_BTN_HOVER,
            corner_radius=7, height=36, command=self._on_iniciar
        )
        self.btn_iniciar.pack(padx=18, pady=(0, 10), fill="x")

        self.btn_detener = ctk.CTkButton(
            left, text="⏹  Detener",
            font=FONT_BTN, fg_color=COLOR_BTN_STOP, hover_color=COLOR_BTN_STOP_HOVER,
            corner_radius=7, height=36, command=self._on_detener
        )
        self.btn_detener.pack(padx=18, pady=(0, 24), fill="x")

        # ── Botón Configurar Credenciales ──────────────────────
        self.btn_config = ctk.CTkButton(
            left, text="🔧  Configurar Credenciales",
            font=FONT_BTN, fg_color=COLOR_BTN_CONFIG, hover_color=COLOR_BTN_CONFIG_HOV,
            corner_radius=7, height=36, command=self._on_config_credenciales
        )
        self.btn_config.pack(side="bottom", fill="x", padx=18, pady=(0, 10))

        # ── Footer ───────────────────────────────────────────────
        self.lbl_footer = ctk.CTkLabel(
            left, text="Listo.",
            font=FONT_FOOTER, text_color=COLOR_TEXT_DIM
        )
        self.lbl_footer.pack(side="bottom", fill="x", padx=18, pady=(0, 10))

    def _build_panel_derecho(self):
        right = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        # Título
        ctk.CTkLabel(
            right, text="LISTADO DE PEDIDOS",
            font=("Segoe UI", 20, "bold"), text_color=COLOR_TEXT
        ).grid(row=0, column=0, pady=(0, 15))

        # Tabla de visualización (CTkTable)
        self.table_pedidos = CTkTable(
            right,
            headers=["#", "Vendedor", "Cliente", "Monto", "Estado"],
            col_weights=[2, 2, 3, 2, 2]
        )
        self.table_pedidos.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

    # ──────────────────────────────────────────────────────────────
    # ACCIONES DE LOS CHECKBOXES
    # ──────────────────────────────────────────────────────────────

    def _on_check_sonido(self):
        if self.check_sonido_var.get() == "on":
            ejecutar_en_hilo(alerta_sonora)

    def _on_check_lectura(self):
        if self.check_lectura_var.get() == "on":
            ejecutar_async_en_hilo("La lectura de mensajes está activada.")

    # ──────────────────────────────────────────────────────────────
    # HANDLERS DE CONTROL
    # ──────────────────────────────────────────────────────────────

    def _on_config_credenciales(self):
        VentanaCredenciales(self, on_guardado=self._on_credenciales_guardadas)

    def _on_credenciales_guardadas(self):
        self._log_console("[OK] Credenciales de NODO guardadas correctamente.", "ok")
        self.lbl_footer.configure(text="Listo.")

    def _on_iniciar(self):
        if not credenciales_configuradas():
            self._log_console("[WARN] Configura las credenciales de NODO antes de iniciar.", "warn")
            return
        if self.worker.is_running():
            self._log_console("[INFO] La sincronización ya está en ejecución.", "info")
            return
        self.lbl_footer.configure(text="Sincronizando...")
        self.btn_iniciar.configure(state="disabled")
        self.btn_config.configure(state="disabled")
        self.worker.start()

    def _on_detener(self):
        if self.worker.is_running():
            self._log_console("[INFO] Deteniendo sincronización...", "warn")
            self.worker.reset()
            self.lbl_footer.configure(text="Proceso detenido.")
            self.btn_iniciar.configure(state="normal")
            self.btn_config.configure(state="normal")
        else:
            self._log_console("[INFO] El proceso no está activo.", "info")

    def _log_console(self, text: str, tag: str = ""):
        # Imprimir logs a la consola de terminal estándar ya que la GUI no la muestra
        clean_text = text.strip()
        print(f"[{tag.upper() if tag else 'LOG'}] {clean_text}")
        
        # Reflejar el log relevante como estado en el pie de página (footer)
        if tag in ["warn", "error"] or "✔" in clean_text or "INFO" in clean_text or "AUTH" in clean_text:
            self.lbl_footer.configure(text=clean_text[:50])

    def _classify_tag(self, m: str) -> str:
        if re.search(r'\[ERROR|ERROR CRÍTICO\]', m): return "error"
        if re.search(r'[✔]|\[OK\]', m): return "ok"
        if re.search(r'\[AVISO\]|\[PAUSA\]|\[WARN\]', m): return "warn"
        return "info"

    def _poll_queue(self):
        try:
            while True:
                msg = self.worker.log_queue.get_nowait()
                if msg != "__DONE__":
                    self._log_console(msg, self._classify_tag(msg))
                else:
                    self.lbl_footer.configure(text="Listo.")
                    self.btn_iniciar.configure(state="normal")
                    self.btn_config.configure(state="normal")
                    self.cargar_datos_excel()
        except queue.Empty:
            pass
        # Drenar cola de latencia para prevenir fugas de memoria
        try:
            while True:
                self.worker.latency_queue.get_nowait()
        except queue.Empty:
            pass
        self.after(POLL_INTERVAL_MS, self._poll_queue)

    def cargar_datos_excel(self):
        """Carga los datos del Excel y los muestra en la tabla"""
        try:
            # Determinar el directorio raíz
            if getattr(sys, 'frozen', False):
                root_dir = os.path.dirname(os.path.abspath(sys.executable))
            else:
                root_dir = os.path.dirname(os.path.abspath(__file__))
            
            filepath = os.path.join(root_dir, "reporte_pedidos.xlsx")
            alt_filepath = os.path.join(root_dir, "reporte_pedidos_NUEVO.xlsx")
            
            # Intentar renombrar reporte_pedidos_NUEVO.xlsx a reporte_pedidos.xlsx si ya no está bloqueado
            if os.path.exists(alt_filepath):
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    os.rename(alt_filepath, filepath)
                    self._log_console("[INFO] Se aplicó la descarga alternativa de pedidos.", "info")
                except Exception as e:
                    print(f"DEBUG: No se pudo renombrar: {e}")
            
            used_path = filepath
            if not os.path.exists(filepath) and os.path.exists(alt_filepath):
                used_path = alt_filepath
                
            if not os.path.exists(used_path):
                print(f"DEBUG: No existe el archivo: {used_path}")
                return
                
            print(f"DEBUG: Leyendo archivo: {used_path}")
            
            # Leer excel de forma segura liberando el handle
            try:
                with open(used_path, "rb") as f:
                    df = pd.read_excel(f)
            except PermissionError:
                self._log_console("[WARN] El archivo 'reporte_pedidos.xlsx' está abierto en Excel. Ciérrelo para actualizar.", "warn")
                self.lbl_footer.configure(text="⚠ Archivo bloqueado por Excel.")
                # Si no podemos leer el original, intentamos leer el alternativo si existe
                if os.path.exists(alt_filepath):
                    with open(alt_filepath, "rb") as f:
                        df = pd.read_excel(f)
                else:
                    return
            except Exception as e:
                print(f"DEBUG: Error al leer Excel: {e}")
                return

            if df is None or df.empty:
                print("DEBUG: DataFrame vacío")
                return
                
            print(f"DEBUG: Columnas encontradas: {df.columns.tolist()}")
            
            df.columns = df.columns.str.strip()
            
            # Limpiar filas donde 'Factura' sea nulo
            if 'Factura' in df.columns:
                df = df.dropna(subset=['Factura'])
                df = df.drop_duplicates(subset=['Factura'])
                
                # Invertir el orden (más nuevos arriba)
                df = df.iloc[::-1]
                
                print(f"DEBUG: Procesando {len(df)} filas")
                
                # Limpiar tabla existente
                self.table_pedidos.clear()

                # Agregar filas
                for idx, row in df.iterrows():
                    factura = str(row.get('Factura', '')).strip()
                    if factura == 'nan' or not factura:
                        continue
                        
                    vendedor = str(row.get('Vendedor', '')).strip()
                    cliente = str(row.get('Cliente', '')).strip()
                    
                    total = row.get('Total', '')
                    moneda = str(row.get('Moneda', '')).strip()
                    
                    # Formatear el importe numérico con separador de miles y decimal
                    if pd.notna(total):
                        try:
                            total_val = float(total)
                            if total_val.is_integer():
                                total_val = int(total_val)
                            
                            if isinstance(total_val, (int, float)):
                                if 'gs' in moneda.lower() or 'guaranies' in moneda.lower():
                                    # Guaraníes no lleva decimales
                                    monto = f"{int(total_val):,}".replace(",", ".") + f" {moneda}"
                                else:
                                    # Dólares lleva 2 decimales
                                    if total_val == int(total_val):
                                        monto = f"{int(total_val):,}".replace(",", ".") + f",00 {moneda}"
                                    else:
                                        parts = f"{total_val:,.2f}".split(".")
                                        thousands = parts[0].replace(",", ".")
                                        decimals = parts[1]
                                        monto = f"{thousands},{decimals} {moneda}"
                            else:
                                monto = f"{total_val} {moneda}"
                        except Exception as e:
                            print(f"DEBUG: Error formateando monto: {e}")
                            monto = f"{total} {moneda}"
                    else:
                        monto = f"{moneda}" if moneda else ""
                        
                    estado = str(row.get('EstadoTransaccion', '')).strip()
                    
                    self.table_pedidos.add_row([factura, vendedor, cliente, monto, estado])
                
                # Forzar un único re-layout al finalizar
                self.update_idletasks()
                print(f"DEBUG: Tabla actualizada con {len(self.table_pedidos.rows)} filas")
            else:
                print("DEBUG: No se encontró la columna 'Factura'")
                
        except Exception as e:
            print(f"Error al cargar excel en tabla: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    app = App()
    app.mainloop()
