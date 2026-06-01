import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
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
COLOR_STATUS_CANCELLED = "#e74c3c"
COLOR_TABLE_HEADER   = "#1e1e3a"
COLOR_TABLE_ROW_EVEN = "#0c0c18"
COLOR_TABLE_ROW_ODD  = "#10101f"
COLOR_SCROLLBAR_BG   = "#1a1a2e"
COLOR_SCROLLBAR_HANDLE = "#2a2a4a"
COLOR_SCROLLBAR_HOVER = "#3a3a6a"
COLOR_GRID_LINE      = "#4a4a6a"

FONT_APP_TITLE  = ("Segoe UI", 15, "bold")
FONT_SECTION    = ("Segoe UI", 10, "bold")
FONT_LABEL      = ("Segoe UI", 11)
FONT_BTN        = ("Segoe UI", 11, "bold")
FONT_TABLE      = ("Segoe UI", 11)
FONT_TABLE_HEADER = ("Segoe UI", 11, "bold")
FONT_FOOTER     = ("Segoe UI", 10)

POLL_INTERVAL_MS = 200

# ── Configuración de Audio ─────────────────────────────────────────────────
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
# VENTANA DE CONFIGURACIÓN DE CREDENCIALES
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


# ══════════════════════════════════════════════════════════════════════════════
# COMPONENTE MODERN TABLE (Estilo Excel con bordes, sin scrollbar horizontal)
# ══════════════════════════════════════════════════════════════════════════════

class ModernTable(ctk.CTkFrame):
    """Tabla estilo Excel con bordes de celdas visibles y adaptable a la ventana"""
    
    def __init__(self, parent, headers, **kwargs):
        super().__init__(parent, fg_color=COLOR_BG, corner_radius=0, **kwargs)
        
        self.headers = headers
        self.parent_frame = parent
        
        # Frame contenedor principal
        self.table_container = ctk.CTkFrame(self, fg_color="transparent")
        self.table_container.pack(fill="both", expand=True)
        
        # Scrollbar vertical solamente
        self.v_scrollbar = ttk.Scrollbar(
            self.table_container,
            orient="vertical"
        )
        self.v_scrollbar.pack(side="right", fill="y")
        
        # Treeview sin scrollbar horizontal
        self.tree = ttk.Treeview(
            self.table_container,
            columns=headers,
            show="headings",
            selectmode="browse",
            yscrollcommand=self.v_scrollbar.set
        )
        
        self.v_scrollbar.config(command=self.tree.yview)
        self.tree.pack(side="left", fill="both", expand=True)
        
        # Configurar columnas con peso variable para que se adapten
        for idx, header in enumerate(headers):
            self.tree.heading(header, text=header)
            # Anchos iniciales pero que se adaptarán
            if idx == 0:  # Factura
                self.tree.column(header, width=140, minwidth=120, anchor="center")
            elif idx == 1:  # Vendedor
                self.tree.column(header, width=160, minwidth=120, anchor="w")
            elif idx == 2:  # Cliente
                self.tree.column(header, width=250, minwidth=180, anchor="w")
            elif idx == 3:  # Monto
                self.tree.column(header, width=120, minwidth=100, anchor="center")
            elif idx == 4:  # Estado
                self.tree.column(header, width=120, minwidth=100, anchor="center")
        
        # Configurar estilos estilo Excel
        style = ttk.Style()
        style.theme_use("clam")
        
        # Estilo para las celdas (con bordes)
        style.configure("Excel.Treeview",
                        background=COLOR_TABLE_ROW_ODD,
                        foreground=COLOR_TEXT,
                        fieldbackground=COLOR_TABLE_ROW_ODD,
                        font=FONT_TABLE,
                        rowheight=32,
                        borderwidth=1,
                        relief="solid")
        
        # Configurar bordes para las celdas
        style.layout("Excel.Treeview", [
            ('Treeview.field', {'sticky': 'nswe', 'border': 1, 'children': [
                ('Treeview.padding', {'sticky': 'nswe', 'children': [
                    ('Treeview.treearea', {'sticky': 'nswe'})
                ]})
            ]})
        ])
        
        # Estilo para los encabezados
        style.configure("Excel.Treeview.Heading",
                        background=COLOR_TABLE_HEADER,
                        foreground=COLOR_TEXT,
                        font=FONT_TABLE_HEADER,
                        relief="solid",
                        borderwidth=1,
                        bordercolor=COLOR_GRID_LINE)
        
        style.map("Excel.Treeview.Heading",
                  background=[("active", COLOR_ACCENT)])
        
        style.map("Excel.Treeview",
                  background=[("selected", COLOR_ACCENT)],
                  foreground=[("selected", COLOR_TEXT)])
        
        # Estilo para scrollbar vertical
        style.configure("Excel.Vertical.TScrollbar",
                        background=COLOR_SCROLLBAR_BG,
                        troughcolor=COLOR_SCROLLBAR_BG,
                        bordercolor=COLOR_BORDER,
                        lightcolor=COLOR_SCROLLBAR_HANDLE,
                        darkcolor=COLOR_SCROLLBAR_HANDLE,
                        arrowcolor=COLOR_TEXT_DIM,
                        width=10)
        
        style.map("Excel.Vertical.TScrollbar",
                  background=[("active", COLOR_SCROLLBAR_HOVER)],
                  lightcolor=[("active", COLOR_SCROLLBAR_HOVER)],
                  darkcolor=[("active", COLOR_SCROLLBAR_HOVER)])
        
        self.v_scrollbar.configure(style="Excel.Vertical.TScrollbar")
        self.tree.configure(style="Excel.Treeview")
        
        # Configurar tags para colores de filas y estados
        self.tree.tag_configure("odd", background=COLOR_TABLE_ROW_ODD)
        self.tree.tag_configure("even", background=COLOR_TABLE_ROW_EVEN)
        self.tree.tag_configure("completed", foreground=COLOR_STATUS_OK)
        self.tree.tag_configure("pending", foreground=COLOR_STATUS_RUN)
        self.tree.tag_configure("cancelled", foreground=COLOR_STATUS_CANCELLED)
        
        self.row_counter = 0
        
        # Bind para redimensionar columnas cuando cambia el tamaño
        self.bind("<Configure>", self._on_resize)
    
    def _on_resize(self, event):
        """Redimensiona las columnas cuando la ventana cambia de tamaño"""
        if hasattr(self, '_resize_after') and self._resize_after:
            self.after_cancel(self._resize_after)
        self._resize_after = self.after(100, self._do_resize)
    
    def _do_resize(self):
        """Aplica la redimensión de columnas basada en el ancho disponible"""
        total_width = self.tree.winfo_width()
        if total_width <= 0:
            return
        
        # Distribución proporcional del ancho total
        # Factura: 15%, Vendedor: 18%, Cliente: 35%, Monto: 15%, Estado: 17%
        widths = [
            int(total_width * 0.15),  # Factura
            int(total_width * 0.18),  # Vendedor
            int(total_width * 0.35),  # Cliente
            int(total_width * 0.15),  # Monto
            int(total_width * 0.17)   # Estado
        ]
        
        # Asegurar anchos mínimos
        min_widths = [120, 120, 180, 100, 100]
        for i in range(len(widths)):
            if widths[i] < min_widths[i]:
                widths[i] = min_widths[i]
        
        # Aplicar nuevos anchos
        for idx, header in enumerate(self.headers):
            self.tree.column(header, width=widths[idx])
        
        self._resize_after = None
    
    def clear(self):
        """Elimina todas las filas de la tabla"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.row_counter = 0
    
    def add_row(self, row_data):
        """Agrega una fila a la tabla con alternancia de colores"""
        tag = "even" if self.row_counter % 2 == 0 else "odd"
        
        # Determinar tag adicional por estado
        estado = str(row_data[4]).lower() if len(row_data) > 4 else ""
        status_tag = ""
        
        if "completado" in estado or "finiquitado" in estado:
            status_tag = "completed"
        elif "pendiente" in estado:
            status_tag = "pending"
        elif "anulado" in estado or "cancelado" in estado:
            status_tag = "cancelled"
        
        # Combinar tags
        final_tag = (tag, status_tag) if status_tag else (tag,)
        
        self.tree.insert("", "end", values=row_data, tags=final_tag)
        self.row_counter += 1
    
    def get_row_count(self):
        return len(self.tree.get_children())
    
    def scroll_to_top(self):
        """Desplaza el scroll hacia arriba"""
        self.tree.yview_moveto(0.0)
    
    def scroll_to_bottom(self):
        """Desplaza el scroll hacia abajo"""
        self.tree.yview_moveto(1.0)


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

        # Tamaño inicial
        self.geometry("1200x750")
        self.minsize(900, 600)
        self.configure(fg_color=COLOR_BG)

        self.worker = SyncWorker()
        self._factura_count = 0
        self._loading_data = False

        self._build_ui()
        self._poll_queue()
        self._verificar_credenciales_al_inicio()
        
        self.after(500, self.cargar_datos_excel)

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
        left = ctk.CTkFrame(self, width=280, fg_color=COLOR_PANEL, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)

        ctk.CTkLabel(
            left, text="P E D I D O S",
            font=FONT_APP_TITLE, text_color=COLOR_TEXT
        ).pack(padx=18, pady=(22, 2), anchor="w")

        ctk.CTkLabel(
            left, text="Alerta de nuevos pedidos en NODO",
            font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM
        ).pack(padx=18, pady=(0, 24), anchor="w")

        self.check_sonido_var = ctk.StringVar(value="off")
        self.check_sonido = ctk.CTkCheckBox(
            left, text="Sonido de notificación",
            font=FONT_LABEL, text_color=COLOR_TEXT,
            variable=self.check_sonido_var, onvalue="on", offvalue="off",
            command=self._on_check_sonido
        )
        self.check_sonido.pack(padx=18, pady=(0, 16), anchor="w")

        self.check_lectura_var = ctk.StringVar(value="off")
        self.check_lectura = ctk.CTkCheckBox(
            left, text="Lectura de mensajes",
            font=FONT_LABEL, text_color=COLOR_TEXT,
            variable=self.check_lectura_var, onvalue="on", offvalue="off",
            command=self._on_check_lectura
        )
        self.check_lectura.pack(padx=18, pady=(0, 24), anchor="w")

        self.btn_iniciar = ctk.CTkButton(
            left, text="▶  Iniciar Sincronización",
            font=FONT_BTN, fg_color=COLOR_BTN_BLUE, hover_color=COLOR_BTN_HOVER,
            corner_radius=7, height=40, command=self._on_iniciar
        )
        self.btn_iniciar.pack(padx=18, pady=(0, 10), fill="x")

        self.btn_detener = ctk.CTkButton(
            left, text="⏹  Detener",
            font=FONT_BTN, fg_color=COLOR_BTN_STOP, hover_color=COLOR_BTN_STOP_HOVER,
            corner_radius=7, height=40, command=self._on_detener
        )
        self.btn_detener.pack(padx=18, pady=(0, 24), fill="x")

        self.btn_config = ctk.CTkButton(
            left, text="🔧  Configurar Credenciales",
            font=FONT_BTN, fg_color=COLOR_BTN_CONFIG, hover_color=COLOR_BTN_CONFIG_HOV,
            corner_radius=7, height=40, command=self._on_config_credenciales
        )
        self.btn_config.pack(side="bottom", fill="x", padx=18, pady=(0, 15))

        self.lbl_footer = ctk.CTkLabel(
            left, text="Listo.",
            font=FONT_FOOTER, text_color=COLOR_TEXT_DIM
        )
        self.lbl_footer.pack(side="bottom", fill="x", padx=18, pady=(0, 15))

    def _build_panel_derecho(self):
        right = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        header_frame = ctk.CTkFrame(right, fg_color="transparent")
        header_frame.grid(row=0, column=0, pady=(0, 15), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)
        header_frame.grid_columnconfigure(2, weight=0)
        
        ctk.CTkLabel(
            header_frame, text="LISTADO DE PEDIDOS",
            font=("Segoe UI", 20, "bold"), text_color=COLOR_TEXT
        ).grid(row=0, column=0, sticky="w")
        
        self.lbl_pedidos_count = ctk.CTkLabel(
            header_frame, text="0 pedidos",
            font=("Segoe UI", 12), text_color=COLOR_TEXT_DIM
        )
        self.lbl_pedidos_count.grid(row=0, column=1, sticky="e", padx=(0, 10))
        
        # Botón para ir al inicio del scroll
        self.btn_scroll_top = ctk.CTkButton(
            header_frame, text="▲ Ir arriba", width=100, height=30,
            font=("Segoe UI", 10), fg_color=COLOR_ACCENT,
            hover_color=COLOR_BORDER, command=self._scroll_to_top
        )
        self.btn_scroll_top.grid(row=0, column=2, sticky="e")

        # Tabla estilo Excel que se adapta al tamaño
        self.table_pedidos = ModernTable(
            right,
            headers=["#", "Vendedor", "Cliente", "Monto", "Estado"]
        )
        self.table_pedidos.grid(row=1, column=0, sticky="nsew")
    
    def _scroll_to_top(self):
        """Desplaza la tabla hacia arriba"""
        self.table_pedidos.scroll_to_top()

    # ──────────────────────────────────────────────────────────────
    # ACCIONES
    # ──────────────────────────────────────────────────────────────

    def _on_check_sonido(self):
        if self.check_sonido_var.get() == "on":
            ejecutar_en_hilo(alerta_sonora)

    def _on_check_lectura(self):
        if self.check_lectura_var.get() == "on":
            ejecutar_async_en_hilo("La lectura de mensajes está activada.")

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
        clean_text = text.strip()
        print(f"[{tag.upper() if tag else 'LOG'}] {clean_text}")
        
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
        try:
            while True:
                self.worker.latency_queue.get_nowait()
        except queue.Empty:
            pass
        self.after(POLL_INTERVAL_MS, self._poll_queue)

    def cargar_datos_excel(self):
        """Carga los datos del Excel y los muestra en la tabla"""
        if self._loading_data:
            return
        
        self._loading_data = True
        
        try:
            if getattr(sys, 'frozen', False):
                root_dir = os.path.dirname(os.path.abspath(sys.executable))
            else:
                root_dir = os.path.dirname(os.path.abspath(__file__))
            
            filepath = os.path.join(root_dir, "reporte_pedidos.xlsx")
            alt_filepath = os.path.join(root_dir, "reporte_pedidos_NUEVO.xlsx")
            
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
                return
                
            df = None
            try:
                with open(used_path, "rb") as f:
                    df = pd.read_excel(f)
            except PermissionError:
                self._log_console("[WARN] El archivo está abierto en Excel. Ciérrelo para actualizar.", "warn")
                self.lbl_footer.configure(text="⚠ Archivo bloqueado por Excel.")
                if os.path.exists(alt_filepath):
                    with open(alt_filepath, "rb") as f:
                        df = pd.read_excel(f)
                else:
                    return
            except Exception as e:
                print(f"DEBUG: Error al leer Excel: {e}")
                return

            if df is None or df.empty:
                return
                
            df.columns = df.columns.str.strip()
            
            if 'Factura' in df.columns:
                df = df.dropna(subset=['Factura'])
                df = df.drop_duplicates(subset=['Factura'])
                df = df.iloc[::-1]
                
                self.table_pedidos.clear()
                
                for idx, row in df.iterrows():
                    factura = str(row.get('Factura', '')).strip()
                    if factura == 'nan' or not factura:
                        continue
                        
                    vendedor = str(row.get('Vendedor', '')).strip()
                    cliente = str(row.get('Cliente', '')).strip()
                    
                    total = row.get('Total', '')
                    moneda = str(row.get('Moneda', '')).strip()
                    
                    if pd.notna(total):
                        try:
                            total_val = float(total)
                            if total_val.is_integer():
                                total_val = int(total_val)
                            
                            if isinstance(total_val, (int, float)):
                                if 'gs' in moneda.lower() or 'guaranies' in moneda.lower():
                                    monto = f"{int(total_val):,}".replace(",", ".") + f" {moneda}"
                                else:
                                    if total_val == int(total_val):
                                        monto = f"{int(total_val):,}".replace(",", ".") + f",00 {moneda}"
                                    else:
                                        parts = f"{total_val:,.2f}".split(".")
                                        thousands = parts[0].replace(",", ".")
                                        decimals = parts[1]
                                        monto = f"{thousands},{decimals} {moneda}"
                            else:
                                monto = f"{total_val} {moneda}"
                        except Exception:
                            monto = f"{total} {moneda}"
                    else:
                        monto = f"{moneda}" if moneda else ""
                        
                    estado = str(row.get('EstadoTransaccion', '')).strip()
                    
                    self.table_pedidos.add_row([factura, vendedor, cliente, monto, estado])
                    
                    if self.table_pedidos.get_row_count() % 50 == 0:
                        self.update_idletasks()
                
                pedidos_count = self.table_pedidos.get_row_count()
                self.lbl_pedidos_count.configure(text=f"{pedidos_count} pedidos")
                self.update_idletasks()
                
                # Forzar redimensión de columnas
                self.table_pedidos._do_resize()
                
                # Scroll hacia arriba después de cargar los datos
                self.table_pedidos.scroll_to_top()
                
        except Exception as e:
            print(f"Error al cargar excel: {e}")
        finally:
            self._loading_data = False


if __name__ == "__main__":
    app = App()
    app.mainloop()