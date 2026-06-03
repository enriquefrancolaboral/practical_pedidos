#!/usr/bin/env python
# app.py - Aplicación principal

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import threading
import os
import sys
import json
from datetime import datetime
from threading import Timer
from collections import deque

PREFS_PATH = os.path.join(os.environ.get('APPDATA', '.'), 'PracticalPedidos', 'preferencias.json')

from core.modelos import Credenciales
from core.estado_pedidos import GestorEstadoPedidos
from presentation.componentes.tabla import ModernTable
from utils.path_utils import resource_path
from utils.logger import log as log_archivo  # RF-30

# Colores
COLOR_BG             = "#0e0e1a"
COLOR_PANEL          = "#13132b"
COLOR_ACCENT         = "#1a1a40"
COLOR_BORDER         = "#2a2a55"
COLOR_BTN_BLUE       = "#1a56db"
COLOR_BTN_HOVER      = "#1e6ef5"
COLOR_BTN_CONFIG     = "#2d4a22"
COLOR_BTN_CONFIG_HOV = "#3a6b2a"
COLOR_TEXT           = "#e8eaf6"
COLOR_TEXT_DIM       = "#8892a4"

FONT_APP_TITLE = ("Segoe UI", 15, "bold")
FONT_LABEL     = ("Segoe UI", 11)
FONT_BTN       = ("Segoe UI", 11, "bold")
FONT_SMALL     = ("Segoe UI", 9)
FONT_SMALL_DIM = ("Segoe UI", 9)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("PRACTICAL PEDIDOS")

        try:
            icon_path = resource_path(os.path.join("presentation", "assets", "icono.ico"))
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception as e:
            print(f"No se pudo cargar el icono: {e}")

        self.geometry("1200x750")
        self.minsize(1010, 600)
        self.configure(fg_color=COLOR_BG)

        self.estado_conexion = "Iniciando..."

        from data.repositorio_pedidos import RepositorioPedidos
        self.repositorio    = RepositorioPedidos()
        self.gestor_estado  = GestorEstadoPedidos(log_fn=self._log)
        self.sync_en_progreso   = False
        self.timer_proximo: Timer = None
        self.primera_sincronizacion = True

        # Historial de hasta 10 sincronizaciones exitosas (RF mod)
        self._historial_sync: deque = deque(maxlen=10)

        # Cuenta regresiva
        self._segundos_restantes: int = 0
        self._timer_countdown: str | None = None  # after-id

        self._prefs = self._cargar_preferencias()

        self._build_ui()
        self._verificar_credenciales()

        self._log("[APP] Aplicación iniciada.")
        self._cargar_tabla_desde_estado_guardado()

        self.after(200, self._lanzar_sincronizacion_en_hilo)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ------------------------------------------------------------------
    # Logging (RF-30)
    # ------------------------------------------------------------------
    def _log(self, mensaje: str):
        log_archivo(mensaje)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _verificar_credenciales(self):
        from utils.credentials import credenciales_configuradas
        if not credenciales_configuradas():
            self.lbl_footer.configure(text="⚠ Credenciales no configuradas.")
            self.estado_conexion = "Sin credenciales"
            self._actualizar_ui_estado()

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

        ctk.CTkLabel(left, text="PEDIDOS", font=FONT_APP_TITLE,
                     text_color=COLOR_TEXT).pack(padx=18, pady=(22, 2), anchor="w")
        ctk.CTkLabel(left, text="Alerta de nuevos pedidos en NODO",
                     font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM
                     ).pack(padx=18, pady=(0, 24), anchor="w")

        self.check_sonido_var = ctk.StringVar(value=self._prefs.get("sonido", "off"))
        self.check_sonido = ctk.CTkCheckBox(
            left, text="Sonido de notificación", font=FONT_LABEL, text_color=COLOR_TEXT,
            variable=self.check_sonido_var, onvalue="on", offvalue="off",
            command=self._on_check_sonido,
        )
        self.check_sonido.pack(padx=18, pady=(0, 16), anchor="w")

        self.check_lectura_var = ctk.StringVar(value=self._prefs.get("lectura", "off"))
        self.check_lectura = ctk.CTkCheckBox(
            left, text="Lectura de mensajes", font=FONT_LABEL, text_color=COLOR_TEXT,
            variable=self.check_lectura_var, onvalue="on", offvalue="off",
            command=self._on_check_lectura,
        )
        self.check_lectura.pack(padx=18, pady=(0, 24), anchor="w")

        # Estado de conexión
        self.lbl_estado_conexion = ctk.CTkLabel(
            left, text="Estado: Iniciando...",
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
            wraplength=220, anchor="w",
        )
        self.lbl_estado_conexion.pack(padx=18, pady=(0, 4), anchor="w")

        # Cuenta regresiva
        self.lbl_countdown = ctk.CTkLabel(
            left, text="Próxima sincronización: --",
            font=FONT_SMALL, text_color=COLOR_TEXT_DIM,
            wraplength=220, anchor="w",
        )
        self.lbl_countdown.pack(padx=18, pady=(0, 12), anchor="w")

        # ── Historial de sincronizaciones ──────────────────────────────
        ctk.CTkLabel(
            left, text="Historial de sincronizaciones",
            font=("Segoe UI", 10, "bold"), text_color=COLOR_TEXT_DIM,
        ).pack(padx=18, pady=(0, 4), anchor="w")

        # Frame con fondo ligeramente diferenciado
        hist_frame = ctk.CTkFrame(left, fg_color=COLOR_ACCENT, corner_radius=6)
        hist_frame.pack(padx=14, pady=(0, 16), fill="x")

        self.lbl_historial_items: list[ctk.CTkLabel] = []
        for _ in range(10):
            lbl = ctk.CTkLabel(
                hist_frame, text="",
                font=FONT_SMALL_DIM, text_color="#555577",
                anchor="w",
            )
            lbl.pack(padx=10, pady=1, fill="x", anchor="w")
            self.lbl_historial_items.append(lbl)

        # ── Botones y footer ───────────────────────────────────────────
        self.btn_config = ctk.CTkButton(
            left, text="🔧  Configurar Credenciales", font=FONT_BTN,
            fg_color=COLOR_BTN_CONFIG, hover_color=COLOR_BTN_CONFIG_HOV,
            corner_radius=7, height=40, command=self._on_config_credenciales,
        )
        self.btn_config.pack(side="bottom", fill="x", padx=18, pady=(0, 15))

        self.lbl_footer = ctk.CTkLabel(
            left, text="Listo.", font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM,
            wraplength=220, anchor="w", justify="left",
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

        ctk.CTkLabel(header_frame, text="LISTADO DE PEDIDOS",
                     font=("Segoe UI", 20, "bold"), text_color=COLOR_TEXT
                     ).grid(row=0, column=0, sticky="w")

        self.lbl_pedidos_count = ctk.CTkLabel(
            header_frame, text="0 pedidos",
            font=("Segoe UI", 12), text_color=COLOR_TEXT_DIM,
        )
        self.lbl_pedidos_count.grid(row=0, column=1, sticky="e")

        self.table_pedidos = ModernTable(
            right, headers=["#", "Vendedor", "Cliente", "Monto", "Estado"]
        )
        self.table_pedidos.grid(row=1, column=0, sticky="nsew")

    # ------------------------------------------------------------------
    # Preferencias
    # ------------------------------------------------------------------
    def _cargar_preferencias(self) -> dict:
        try:
            with open(PREFS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _guardar_preferencias(self):
        try:
            os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
            with open(PREFS_PATH, 'w', encoding='utf-8') as f:
                json.dump({
                    "sonido":  self.check_sonido_var.get(),
                    "lectura": self.check_lectura_var.get(),
                }, f)
        except Exception as e:
            self._log(f"[PREFS] Error al guardar preferencias: {e}")

    # ------------------------------------------------------------------
    # Carga inmediata desde estado guardado (RF-32)
    # ------------------------------------------------------------------
    def _cargar_tabla_desde_estado_guardado(self):
        estado = self.gestor_estado.estado_actual
        if estado:
            self._actualizar_tabla([], estado, [])
            self._log(f"[APP] Estado previo cargado en UI: {len(estado)} pedidos.")
        else:
            self._log("[APP] Sin estado previo guardado.")

    # ------------------------------------------------------------------
    # Hilo de sincronización
    # ------------------------------------------------------------------
    def _lanzar_sincronizacion_en_hilo(self):
        threading.Thread(target=self._ejecutar_sincronizacion, daemon=True).start()

    # ------------------------------------------------------------------
    # Checkboxes
    # ------------------------------------------------------------------
    def _on_check_sonido(self):
        from presentation.componentes.audio import alerta_sonora
        if self.check_sonido_var.get() == "on":
            self._log("[CONFIG] Sonido activado - reproduciendo prueba.")
            threading.Thread(target=alerta_sonora, daemon=True).start()
        else:
            self._log("[CONFIG] Sonido desactivado.")
        self._guardar_preferencias()

    def _on_check_lectura(self):
        from presentation.componentes.audio import reproducir_texto
        if self.check_lectura_var.get() == "on":
            self._log("[CONFIG] Lectura activada - probando TTS.")
            threading.Thread(
                target=reproducir_texto,
                args=("La lectura de mensajes está activada",),
                daemon=True,
            ).start()
        else:
            self._log("[CONFIG] Lectura desactivada.")
        self._guardar_preferencias()

    # ------------------------------------------------------------------
    # Credenciales
    # ------------------------------------------------------------------
    def _on_config_credenciales(self):
        from presentation.ventanas.credenciales import VentanaCredenciales
        VentanaCredenciales(self, on_guardado=self._on_credenciales_guardadas)

    def _on_credenciales_guardadas(self):
        self.lbl_footer.configure(text="Credenciales guardadas correctamente.")
        self.after(1000, self._lanzar_sincronizacion_en_hilo)

    # ------------------------------------------------------------------
    # Cuenta regresiva (RF mod 1)
    # ------------------------------------------------------------------
    def _iniciar_countdown(self, segundos: int):
        """Arranca la cuenta regresiva visible en el panel izquierdo."""
        if self._timer_countdown is not None:
            self.after_cancel(self._timer_countdown)
            self._timer_countdown = None
        self._segundos_restantes = segundos
        self._tick_countdown()

    def _tick_countdown(self):
        s = self._segundos_restantes
        if s <= 0:
            self.lbl_countdown.configure(text="Próxima sincronización: ahora")
            return
        mins, secs = divmod(s, 60)
        if mins > 0:
            texto = f"Próxima sincronización: {mins}m {secs:02d}s"
        else:
            texto = f"Próxima sincronización: {secs}s"
        self.lbl_countdown.configure(text=texto)
        self._segundos_restantes -= 1
        self._timer_countdown = self.after(1000, self._tick_countdown)

    # ------------------------------------------------------------------
    # Historial de sincronizaciones (RF mod 2)
    # ------------------------------------------------------------------
    def _registrar_sync_exitosa(self, ts: datetime):
        self._historial_sync.appendleft(ts)
        self._refrescar_historial_ui()

    def _refrescar_historial_ui(self):
        items = list(self._historial_sync)
        for i, lbl in enumerate(self.lbl_historial_items):
            if i < len(items):
                texto = items[i].strftime("%H:%M:%S  —  %d/%m/%Y")
                lbl.configure(text=texto, text_color="#9090b8")
            else:
                lbl.configure(text="", text_color="#555577")

    # ------------------------------------------------------------------
    # Sincronización (RF-07, RF-08, RF-09)
    # ------------------------------------------------------------------
    def _programar_proxima_sincronizacion(self):
        """Programa la próxima sync en el siguiente múltiplo exacto de 5 min (RF-07)."""
        ahora = datetime.now()
        minutos_faltantes  = (5 - (ahora.minute % 5)) % 5
        segundos_faltantes = minutos_faltantes * 60 - ahora.second
        if segundos_faltantes <= 0:
            segundos_faltantes += 300

        self.after(0, lambda: self._iniciar_countdown(segundos_faltantes))

        self.timer_proximo = Timer(segundos_faltantes, self._lanzar_sincronizacion_en_hilo)
        self.timer_proximo.daemon = True
        self.timer_proximo.start()

    def _ejecutar_sincronizacion(self):
        """Corre íntegramente en un hilo background. Actualiza UI via self.after()."""
        from utils.credentials import credenciales_configuradas, cargar_credenciales
        from data.servicio_nodo import ServicioNodo

        if self.sync_en_progreso:
            self._log("[SYNC] Sincronización previa en progreso. Omitiendo.")
            self._programar_proxima_sincronizacion()
            return

        if not credenciales_configuradas():
            self.after(0, lambda: self.lbl_footer.configure(text="⚠ Credenciales no configuradas."))
            self.estado_conexion = "Error: Sin credenciales"
            self.after(0, self._actualizar_ui_estado)
            self._programar_proxima_sincronizacion()
            return

        self.sync_en_progreso = True
        self.estado_conexion = "Conectando..."
        self.after(0, self._actualizar_ui_estado)
        self.after(0, lambda: self.log_ui("Iniciando sincronización..."))

        try:
            user, pwd = cargar_credenciales(self._log)
            if not user or not pwd:
                self.estado_conexion = "Error: Credenciales inválidas"
                self.after(0, lambda: self.log_ui("Error: Credenciales inválidas."))
                self._log("[AUTH] Error de autenticación: credenciales inválidas.")
                return

            credenciales = Credenciales(usuario=user, password=pwd)
            servicio     = ServicioNodo(credenciales, log_fn=self._log)
            resultado    = servicio.sincronizar_pedidos()

            if resultado["exito"]:
                self.estado_conexion = "Conectado"
                ts_sync = datetime.now()

                pedidos_desde_nodo = resultado["pedidos"] or []
                nuevos, modificados, nuevo_estado = \
                    self.gestor_estado.sincronizar_y_detectar_nuevos(pedidos_desde_nodo)

                self.after(0, lambda: self._actualizar_tabla(modificados, nuevo_estado, nuevos))

                # RF-13: no alertar en la primera sincronización
                if not self.primera_sincronizacion:
                    if nuevos:
                        for p in nuevos:
                            self._log(f"[NUEVO PEDIDO] {p.numero_pedido} - {p.vendedor} → {p.cliente}")
                        self._generar_alertas_secuenciales(nuevos)
                else:
                    if nuevos:
                        self._log(
                            f"[INFO] {len(nuevos)} pedido(s) nuevos al iniciar (sin alertas por RF-13)."
                        )

                self.gestor_estado.guardar_estado_actual()
                msg = (f"Sincronización exitosa — "
                       f"{len(nuevos)} nuevo(s), {len(modificados)} modificado(s)")
                self.after(0, lambda: self.log_ui(msg))
                self._log(f"[SYNC] {msg}")

                self.after(0, lambda ts=ts_sync: self._registrar_sync_exitosa(ts))
                self.after(0, self._actualizar_ui_estado)

                if self.primera_sincronizacion:
                    self.primera_sincronizacion = False

            else:
                self.estado_conexion = "Error"
                self.after(0, lambda: self.log_ui(f"Error: {resultado['mensaje']}"))
                self._log(f"[ERROR CONEXIÓN] {resultado['mensaje']}")

        except Exception as e:
            self.estado_conexion = "Error"
            self.after(0, lambda: self.log_ui(f"Error inesperado: {str(e)}"))
            self._log(f"[ERROR] {str(e)}")
        finally:
            self.sync_en_progreso = False
            self.after(0, self._actualizar_ui_estado)
            self._programar_proxima_sincronizacion()

    # ------------------------------------------------------------------
    # Tabla
    # ------------------------------------------------------------------
    def _actualizar_tabla(self, pedidos_modificados: list, todos: dict, nuevos: list):
        self.table_pedidos.clear()

        pedidos_ordenados = sorted(todos.values(), key=lambda p: p.fecha, reverse=True)
        nuevos_numeros    = {p.numero_pedido for p in nuevos}
        alertados         = self.gestor_estado.pedidos_alertados

        for pedido in pedidos_ordenados:
            monto = f"{int(pedido.total):,}".replace(",", ".")
            if pedido.moneda:
                monto += f" {pedido.moneda}"

            numero = pedido.numero_pedido
            if pedido.numero_pedido in nuevos_numeros:
                numero = f"{numero} [New]"
            elif pedido.numero_pedido in alertados:
                numero = f"{numero} 🔊"

            self.table_pedidos.add_row([
                numero, pedido.vendedor, pedido.cliente, monto, pedido.estado
            ])

        self.lbl_pedidos_count.configure(text=f"{len(pedidos_ordenados)} pedidos")
        self.table_pedidos.scroll_to_top()

    def _refrescar_iconos_tabla(self):
        estado = self.gestor_estado.estado_actual
        if estado:
            self._actualizar_tabla([], estado, [])

    # ------------------------------------------------------------------
    # Alertas serializadas sin solapamiento (RF-14 – RF-20, RF-28)
    # ------------------------------------------------------------------
    def _generar_alertas_secuenciales(self, pedidos: list):
        """Un único hilo reproduce todas las alertas en serie."""
        from presentation.componentes.audio import alerta_sonora, reproducir_texto
        def cola():
            for pedido in pedidos:
                alerto = False
                if self.check_sonido_var.get() == "on":
                    alerta_sonora()
                    alerto = True
                if self.check_lectura_var.get() == "on":
                    reproducir_texto(
                        f"El vendedor {pedido.vendedor} ha cargado "
                        f"un pedido para {pedido.cliente}"
                    )
                    alerto = True
                if alerto:
                    self.gestor_estado.marcar_como_alertado(pedido.numero_pedido)
                    self.after(0, self._refrescar_iconos_tabla)

        threading.Thread(target=cola, daemon=True).start()

    # ------------------------------------------------------------------
    # Estado UI
    # ------------------------------------------------------------------
    def _actualizar_ui_estado(self):
        self.lbl_estado_conexion.configure(text=f"Estado: {self.estado_conexion}")

    def log_ui(self, mensaje: str):
        self.after(0, lambda: self.lbl_footer.configure(text=mensaje))
        print(mensaje)

    # ------------------------------------------------------------------
    # Cierre (RF-31)
    # ------------------------------------------------------------------
    def on_closing(self):
        self._log("[APP] Cerrando aplicación.")
        if self.timer_proximo:
            self.timer_proximo.cancel()
        if self._timer_countdown:
            self.after_cancel(self._timer_countdown)
        self._guardar_preferencias()
        self.gestor_estado.guardar_estado_actual()
        self.destroy()
        sys.exit(0)
