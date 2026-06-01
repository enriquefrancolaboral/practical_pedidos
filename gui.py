import customtkinter as ctk
import queue
import re
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

# ── Tema ──────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Paleta de colores ─────────────────────────────────────────────────────────
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

# ── Tipografía ────────────────────────────────────────────────────────────────
FONT_APP_TITLE  = ("Segoe UI", 15, "bold")
FONT_SECTION    = ("Segoe UI", 10, "bold")
FONT_LABEL      = ("Segoe UI", 11)
FONT_VALUE_LG   = ("Segoe UI", 26, "bold")
FONT_VALUE_MD   = ("Segoe UI", 13, "bold")
FONT_BTN        = ("Segoe UI", 11, "bold")
FONT_CONSOLE    = ("Consolas", 11)
FONT_FOOTER     = ("Segoe UI", 10)

# ── Consola: tamaño de fuente dinámico ────────────────────────────────────────
CONSOLE_FONT_MIN     = 8
CONSOLE_FONT_MAX     = 22
CONSOLE_FONT_DEFAULT = 11

# ── Polling ───────────────────────────────────────────────────────────────────
POLL_INTERVAL_MS = 200


# ══════════════════════════════════════════════════════════════════════════════
# VENTANA DE CONFIGURACIÓN DE CREDENCIALES
# ══════════════════════════════════════════════════════════════════════════════

class VentanaCredenciales(ctk.CTkToplevel):
    def __init__(self, parent, on_guardado=None):
        super().__init__(parent)
        self.title("Configurar Credenciales")
        self.geometry("440x490")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_PANEL)
        self.on_guardado = on_guardado
        # Compartir ícono con la ventana principal
        try:
            self.after(200, lambda: self.iconbitmap(resource_path("icono.ico")))
        except Exception:
            pass
        self.after(20, self._build)

    def _campo_password(self, parent, atributo: str, placeholder: str, pady_bottom: int):
        """Crea una fila con Entry de contraseña + botón ojito."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(padx=28, pady=(0, pady_bottom), fill="x")

        entry = ctk.CTkEntry(row, width=344, show="●", placeholder_text=placeholder)
        entry.pack(side="left")
        setattr(self, atributo, entry)

        # Estado de visibilidad por campo
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
            f, text="Configurar Credenciales",
            font=FONT_APP_TITLE, text_color=COLOR_TEXT
        ).pack(padx=28, pady=(22, 4), anchor="w")

        ctk.CTkLabel(
            f,
            text="Los datos se guardan cifrados en el sistema operativo.\nNunca se escriben en disco como texto plano.",
            font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM, justify="left"
        ).pack(padx=28, pady=(0, 16), anchor="w")

        # ── NODO ──────────────────────────────────────────────────
        ctk.CTkLabel(f, text="NODO — Usuario (email)",
                     font=FONT_SECTION, text_color=COLOR_TEXT_DIM
                     ).pack(padx=28, pady=(0, 2), anchor="w")
        self.entry_nodo_user = ctk.CTkEntry(f, width=384, placeholder_text="usuario@ejemplo.com")
        self.entry_nodo_user.pack(padx=28, pady=(0, 10))

        ctk.CTkLabel(f, text="NODO — Contraseña",
                     font=FONT_SECTION, text_color=COLOR_TEXT_DIM
                     ).pack(padx=28, pady=(0, 2), anchor="w")
        self._campo_password(f, "entry_nodo_pass", "••••••••", pady_bottom=14)

        # ── DIGIP ─────────────────────────────────────────────────
        ctk.CTkLabel(f, text="DIGIP — Usuario",
                     font=FONT_SECTION, text_color=COLOR_TEXT_DIM
                     ).pack(padx=28, pady=(0, 2), anchor="w")
        self.entry_digip_user = ctk.CTkEntry(f, width=384, placeholder_text="usuario_digip")
        self.entry_digip_user.pack(padx=28, pady=(0, 10))

        ctk.CTkLabel(f, text="DIGIP — Contraseña",
                     font=FONT_SECTION, text_color=COLOR_TEXT_DIM
                     ).pack(padx=28, pady=(0, 2), anchor="w")
        self._campo_password(f, "entry_digip_pass", "••••••••", pady_bottom=18)

        self.lbl_error = ctk.CTkLabel(f, text="", font=("Segoe UI", 10),
                                      text_color="#f56565")
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
        du = self.entry_digip_user.get().strip()
        dp = self.entry_digip_pass.get().strip()

        if not all([nu, np, du, dp]):
            self.lbl_error.configure(text="Todos los campos son obligatorios.")
            return

        ok = guardar_credenciales(nu, np, du, dp)
        if ok:
            if self.on_guardado:
                self.on_guardado()
            self.destroy()
        else:
            self.lbl_error.configure(text="Error al guardar. Verifica permisos del sistema.")


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
        self._console_font_size = CONSOLE_FONT_DEFAULT

        self._build_ui()
        self._poll_queue()
        self._verificar_credenciales_al_inicio()

    # ──────────────────────────────────────────────────────────────
    # VERIFICACIÓN INICIAL DE CREDENCIALES
    # ──────────────────────────────────────────────────────────────

    def _verificar_credenciales_al_inicio(self):
        if not credenciales_configuradas():
            self._log_console(
                "[WARN] No se encontraron credenciales. "
                "Configúralas antes de iniciar.\n", "warn"
            )
            self.lbl_footer.configure(text="⚠ Credenciales no configuradas.")

    # ──────────────────────────────────────────────────────────────
    # CONSTRUCCIÓN DE UI
    # ──────────────────────────────────────────────────────────────

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
        ).pack(padx=18, pady=(0, 18), anchor="w")

        self._sep(left)

        # ── Estado ──────────────────────────────────────────────
        ctk.CTkLabel(
            left, text="ESTADO DEL SISTEMA",
            font=FONT_SECTION, text_color=COLOR_TEXT_DIM
        ).pack(padx=18, pady=(16, 4), anchor="w")

        self.lbl_estado = ctk.CTkLabel(
            left, text="● Inactivo",
            font=FONT_VALUE_MD, text_color="#666680"
        )
        self.lbl_estado.pack(padx=18, pady=(0, 16), anchor="w")

        self._sep(left)

        # ── Métricas ─────────────────────────────────────────────
        ctk.CTkLabel(
            left, text="FACTURAS PROCESADAS",
            font=FONT_SECTION, text_color=COLOR_TEXT_DIM
        ).pack(padx=18, pady=(16, 2), anchor="w")

        self.lbl_count = ctk.CTkLabel(
            left, text="0",
            font=FONT_VALUE_LG, text_color=COLOR_TEXT
        )
        self.lbl_count.pack(padx=18, pady=(0, 16), anchor="w")

        ctk.CTkLabel(
            left, text="LATENCIA",
            font=FONT_SECTION, text_color=COLOR_TEXT_DIM
        ).pack(padx=18, pady=(0, 2), anchor="w")

        self.lbl_latencia = ctk.CTkLabel(
            left, text="-- ms",
            font=FONT_VALUE_MD, text_color="#666680"
        )
        self.lbl_latencia.pack(padx=18, pady=(0, 20), anchor="w")

        self._sep(left)

        # ── Botones ──────────────────────────────────────────────
        self.btn_start = ctk.CTkButton(
            left, text="▶  Iniciar Sincronización",
            font=FONT_BTN, fg_color=COLOR_BTN_BLUE, hover_color=COLOR_BTN_HOVER,
            corner_radius=7, height=40, command=self._on_start
        )
        self.btn_start.pack(fill="x", padx=18, pady=(18, 8))

        self.btn_stop = ctk.CTkButton(
            left, text="⏸  Pausar",
            font=FONT_BTN, fg_color=COLOR_BTN_STOP, hover_color=COLOR_BTN_STOP_HOVER,
            corner_radius=7, height=36, state="disabled", command=self._on_stop_toggle
        )
        self.btn_stop.pack(fill="x", padx=18, pady=(0, 8))

        self.btn_reset = ctk.CTkButton(
            left, text="🔄  Forzar Reinicio",
            font=FONT_BTN, fg_color=COLOR_BTN_RESET, hover_color="#3d5166",
            corner_radius=7, height=36, command=self._on_reset
        )
        self.btn_reset.pack(fill="x", padx=18, pady=(0, 8))

        self.btn_config = ctk.CTkButton(
            left, text="🔑  Configurar Credenciales",
            font=FONT_BTN, fg_color=COLOR_BTN_CONFIG, hover_color=COLOR_BTN_CONFIG_HOV,
            corner_radius=7, height=36, command=self._on_config_credenciales
        )
        self.btn_config.pack(fill="x", padx=18, pady=(0, 18))

        # ── Footer ───────────────────────────────────────────────
        self.lbl_footer = ctk.CTkLabel(
            left, text="Listo.",
            font=FONT_FOOTER, text_color=COLOR_TEXT_DIM
        )
        self.lbl_footer.pack(side="bottom", fill="x", padx=18, pady=14)

    def _build_panel_derecho(self):
        right = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        # ── Cabecera de consola ──────────────────────────────────
        header = ctk.CTkFrame(right, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="CONSOLA DE MONITOREO",
            font=FONT_APP_TITLE, text_color=COLOR_TEXT
        ).grid(row=0, column=0, sticky="w")

        # ── Textbox consola ──────────────────────────────────────
        self.txt_console = ctk.CTkTextbox(
            right,
            font=("Consolas", self._console_font_size),
            fg_color=COLOR_CONSOLE,
            text_color="#c5cdd9",
            wrap="word",
            corner_radius=8,
            border_width=1,
            border_color=COLOR_BORDER
        )
        self.txt_console.grid(row=1, column=0, sticky="nsew")
        self.txt_console.configure(state="disabled")

        self.txt_console.tag_config("info",  foreground="#5b9cf6")
        self.txt_console.tag_config("error", foreground="#f56565")
        self.txt_console.tag_config("warn",  foreground="#f6c90e")
        self.txt_console.tag_config("ok",    foreground="#48bb78")
        self.txt_console.tag_config("swal",  foreground="#d87efc")

        self.txt_console.bind("<Control-MouseWheel>", self._on_console_zoom)
        self.txt_console.bind("<Control-Button-4>", lambda e: self._zoom_console(+1))
        self.txt_console.bind("<Control-Button-5>", lambda e: self._zoom_console(-1))

    def _sep(self, parent):
        ctk.CTkFrame(parent, height=1, fg_color=COLOR_BORDER).pack(
            fill="x", padx=18, pady=0
        )

    # ──────────────────────────────────────────────────────────────
    # ZOOM DE CONSOLA
    # ──────────────────────────────────────────────────────────────

    def _on_console_zoom(self, event):
        delta = 1 if event.delta > 0 else -1
        self._zoom_console(delta)

    def _zoom_console(self, delta: int):
        nuevo = self._console_font_size + delta
        nuevo = max(CONSOLE_FONT_MIN, min(CONSOLE_FONT_MAX, nuevo))
        if nuevo != self._console_font_size:
            self._console_font_size = nuevo
            self.txt_console.configure(font=("Consolas", nuevo))

    # ──────────────────────────────────────────────────────────────
    # HANDLERS DE CONTROL
    # ──────────────────────────────────────────────────────────────

    def _on_start(self):
        if not credenciales_configuradas():
            self._log_console(
                "[ERROR] No hay credenciales configuradas. "
                "Usa el botón 'Configurar Credenciales' primero.\n", "error"
            )
            return
        if self.worker.is_running():
            return
        self._factura_count = 0
        self.lbl_count.configure(text="0")
        self.lbl_latencia.configure(text="-- ms", text_color="#666680")
        self.worker.start()
        self._set_estado("running")
        self._log_console("[INFO] Proceso iniciado.\n", "info")

    def _on_stop_toggle(self):
        if self.btn_stop.cget("text") == "⏸  Pausar":
            self.worker.stop()
            self._set_estado("paused")
            self._log_console("[INFO] Pausa solicitada. Se detendrá en el próximo punto seguro.\n", "warn")
        else:
            self.worker.resume()
            self._set_estado("running")

    def _on_reset(self):
        self._log_console("[INFO] Solicitando reinicio completo del sistema.\n", "warn")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="disabled")
        self.btn_reset.configure(state="disabled", text="⟳ Reiniciando.")
        self.update()
        self.worker.reset()
        self._factura_count = 0
        self.lbl_count.configure(text="0")
        self.lbl_latencia.configure(text="-- ms", text_color="#666680")
        self._set_estado("idle")
        self.btn_start.configure(state="normal")
        self.btn_reset.configure(state="normal", text="🔄  Forzar Reinicio")
        self._log_console("[INFO] Sistema reiniciado. Listo para nueva sincronización.\n", "ok")

    def _on_config_credenciales(self):
        VentanaCredenciales(self, on_guardado=self._on_credenciales_guardadas)

    def _on_credenciales_guardadas(self):
        self._log_console("[OK] Credenciales guardadas correctamente en el sistema.\n", "ok")
        self.lbl_footer.configure(text="Listo.")

    # ──────────────────────────────────────────────────────────────
    # ESTADOS VISUALES
    # ──────────────────────────────────────────────────────────────

    def _set_estado(self, estado: str):
        if estado == "running":
            self.lbl_estado.configure(text="● Sincronizando", text_color=COLOR_STATUS_RUN)
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal", text="⏸  Pausar",
                                    fg_color=COLOR_BTN_STOP, hover_color=COLOR_BTN_STOP_HOVER)
            self.lbl_footer.configure(text="Sincronización en curso.")
        elif estado == "paused":
            self.lbl_estado.configure(text="● Pausado", text_color="#ff7043")
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal", text="▶  Reanudar",
                                    fg_color=COLOR_BTN_BLUE, hover_color=COLOR_BTN_HOVER)
            self.lbl_footer.configure(text="Sincronización en pausa.")
        elif estado == "done":
            self.lbl_estado.configure(text="● Completado", text_color=COLOR_STATUS_OK)
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled", text="⏸  Pausar", fg_color=COLOR_BTN_STOP)
            self.lbl_footer.configure(text="Proceso terminado.")
        elif estado == "idle":
            self.lbl_estado.configure(text="● Inactivo", text_color="#666680")
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled", text="⏸  Pausar", fg_color=COLOR_BTN_STOP)
            self.lbl_footer.configure(text="Listo.")

    # ──────────────────────────────────────────────────────────────
    # CONSOLA
    # ──────────────────────────────────────────────────────────────

    def _log_console(self, text: str, tag: str = ""):
        self.txt_console.configure(state="normal")
        if tag:
            self.txt_console.insert("end", text, tag)
        else:
            self.txt_console.insert("end", text)
        self.txt_console.configure(state="disabled")
        self.txt_console.see("end")

    def _classify_tag(self, m: str) -> str:
        if re.search(r'\[ERROR|ERROR CRÍTICO\]', m):
            return "error"
        if re.search(r'[✔]|\[OK\]', m):
            return "ok"
        if '[SWAL2]' in m:
            return "swal"
        if re.search(r'\[AVISO\]|\[PAUSA\]|\[WARN\]', m):
            return "warn"
        if re.search(r'\[INFO\]|→', m):
            return "info"
        return ""

    # ──────────────────────────────────────────────────────────────
    # POLLING DE QUEUES
    # ──────────────────────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while True:
                msg = self.worker.log_queue.get_nowait()
                if msg == "__DONE__":
                    self._set_estado("done")
                    continue
                if "[DIGIP] Todos los ítems cargados para Factura" in msg:
                    self._factura_count += 1
                    self.lbl_count.configure(text=str(self._factura_count))
                self._log_console(msg + "\n", self._classify_tag(msg))
        except queue.Empty:
            pass

        try:
            while True:
                estado, ms = self.worker.latency_queue.get_nowait()
                if estado == "ok":
                    color = "#48bb78" if ms < 500 else "#f6c90e" if ms < 1500 else "#f56565"
                    self.lbl_latencia.configure(text=f"{ms} ms", text_color=color)
                else:
                    self.lbl_latencia.configure(text="Sin red", text_color="#f56565")
        except queue.Empty:
            pass

        self.after(POLL_INTERVAL_MS, self._poll_queue)


if __name__ == "__main__":
    app = App()
    app.mainloop()
