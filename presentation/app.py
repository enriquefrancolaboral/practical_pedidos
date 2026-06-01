#!/usr/bin/env python
# app.py - Aplicación principal

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import threading
import os
import sys
from datetime import datetime
from threading import Timer

from data.repositorio_pedidos import RepositorioPedidos
from data.servicio_nodo import ServicioNodo
from core.modelos import Credenciales
from core.estado_pedidos import GestorEstadoPedidos
from presentation.componentes.tabla import ModernTable
from presentation.componentes.audio import alerta_sonora, reproducir_texto
from presentation.ventanas.credenciales import VentanaCredenciales
from utils.credentials import credenciales_configuradas, cargar_credenciales
from utils.path_utils import resource_path
from utils.logger import log as log_archivo  # RF-30

# Colores
COLOR_BG           = "#0e0e1a"
COLOR_PANEL        = "#13132b"
COLOR_ACCENT       = "#1a1a40"
COLOR_BORDER       = "#2a2a55"
COLOR_BTN_BLUE     = "#1a56db"
COLOR_BTN_HOVER    = "#1e6ef5"
COLOR_BTN_CONFIG   = "#2d4a22"
COLOR_BTN_CONFIG_HOV = "#3a6b2a"
COLOR_TEXT         = "#e8eaf6"
COLOR_TEXT_DIM     = "#8892a4"

FONT_APP_TITLE = ("Segoe UI", 15, "bold")
FONT_LABEL     = ("Segoe UI", 11)
FONT_BTN       = ("Segoe UI", 11, "bold")


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
        self.minsize(900, 600)
        self.configure(fg_color=COLOR_BG)

        # --- CORRECCIÓN #1: estado_conexion inicializado ---
        self.estado_conexion = "Iniciando..."

        self.repositorio = RepositorioPedidos()
        self.gestor_estado = GestorEstadoPedidos(log_fn=self._log)
        self.sync_en_progreso = False
        self.timer_proximo: Timer = None
        self.ultima_sincronizacion: datetime = None
        self.primera_sincronizacion = True

        self._build_ui()
        self._verificar_credenciales()

        # RF-30: registrar inicio
        self._log("[APP] Aplicación iniciada.")

        self.after(500, self._ejecutar_sincronizacion)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ------------------------------------------------------------------
    # Logging centralizado (RF-30)
    # ------------------------------------------------------------------
    def _log(self, mensaje: str):
        """Registra en archivo y consola."""
        log_archivo(mensaje)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _verificar_credenciales(self):
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

        ctk.CTkLabel(left, text="P E D I D O S", font=FONT_APP_TITLE,
                     text_color=COLOR_TEXT).pack(padx=18, pady=(22, 2), anchor="w")
        ctk.CTkLabel(left, text="Alerta de nuevos pedidos en NODO",
                     font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM
                     ).pack(padx=18, pady=(0, 24), anchor="w")

        self.check_sonido_var = ctk.StringVar(value="off")
        self.check_sonido = ctk.CTkCheckBox(
            left, text="Sonido de notificación", font=FONT_LABEL, text_color=COLOR_TEXT,
            variable=self.check_sonido_var, onvalue="on", offvalue="off",
            command=self._on_check_sonido,
        )
        self.check_sonido.pack(padx=18, pady=(0, 16), anchor="w")

        self.check_lectura_var = ctk.StringVar(value="off")
        self.check_lectura = ctk.CTkCheckBox(
            left, text="Lectura de mensajes", font=FONT_LABEL, text_color=COLOR_TEXT,
            variable=self.check_lectura_var, onvalue="on", offvalue="off",
            command=self._on_check_lectura,
        )
        self.check_lectura.pack(padx=18, pady=(0, 24), anchor="w")

        self.lbl_estado_conexion = ctk.CTkLabel(
            left, text="Estado: Iniciando...",
            font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM,
        )
        self.lbl_estado_conexion.pack(padx=18, pady=(0, 5), anchor="w")

        self.lbl_ultima_sync = ctk.CTkLabel(
            left, text="Última sincronización: --",
            font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM,
        )
        self.lbl_ultima_sync.pack(padx=18, pady=(0, 20), anchor="w")

        self.btn_config = ctk.CTkButton(
            left, text="🔧  Configurar Credenciales", font=FONT_BTN,
            fg_color=COLOR_BTN_CONFIG, hover_color=COLOR_BTN_CONFIG_HOV,
            corner_radius=7, height=40, command=self._on_config_credenciales,
        )
        self.btn_config.pack(side="bottom", fill="x", padx=18, pady=(0, 15))

        self.lbl_footer = ctk.CTkLabel(
            left, text="Listo.", font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM,
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
    # Callbacks de checkboxes
    # ------------------------------------------------------------------
    def _on_check_sonido(self):
        if self.check_sonido_var.get() == "on":
            self._log("[CONFIG] Sonido activado - reproduciendo prueba.")
            # --- CORRECCIÓN #2: usar alerta_sonora() en lugar de winsound ---
            threading.Thread(target=alerta_sonora, daemon=True).start()
        else:
            self._log("[CONFIG] Sonido desactivado.")

    def _on_check_lectura(self):
        if self.check_lectura_var.get() == "on":
            self._log("[CONFIG] Lectura activada - probando TTS.")
            reproducir_texto("La lectura de mensajes está activada")
        else:
            self._log("[CONFIG] Lectura desactivada.")

    # ------------------------------------------------------------------
    # Credenciales
    # ------------------------------------------------------------------
    def _on_config_credenciales(self):
        VentanaCredenciales(self, on_guardado=self._on_credenciales_guardadas)

    def _on_credenciales_guardadas(self):
        self.lbl_footer.configure(text="Credenciales guardadas correctamente.")
        self.after(1000, self._ejecutar_sincronizacion)

    # ------------------------------------------------------------------
    # Sincronización (RF-07, RF-08, RF-09)
    # ------------------------------------------------------------------
    def _programar_proxima_sincronizacion(self):
        """Programa la próxima sync en el siguiente múltiplo de 5 minutos exactos (RF-07)."""
        ahora = datetime.now()
        minutos_faltantes = (5 - (ahora.minute % 5)) % 5
        segundos_faltantes = minutos_faltantes * 60 - ahora.second

        # Si ya estamos exactamente en un múltiplo de 5, esperar 5 min más
        if segundos_faltantes <= 0:
            segundos_faltantes += 300

        self.log_ui(f"Próxima sincronización en {segundos_faltantes}s.")
        self.timer_proximo = Timer(segundos_faltantes, self._ejecutar_sincronizacion_en_hilo)
        self.timer_proximo.daemon = True
        self.timer_proximo.start()

    def _ejecutar_sincronizacion_en_hilo(self):
        if self.sync_en_progreso:
            self._log("[SYNC] Sincronización previa en progreso. Omitiendo.")
            self._programar_proxima_sincronizacion()
            return
        self.after(0, self._ejecutar_sincronizacion)

    def _ejecutar_sincronizacion(self):
        if self.sync_en_progreso:
            return

        if not credenciales_configuradas():
            self.lbl_footer.configure(text="⚠ Credenciales no configuradas.")
            self.estado_conexion = "Error: Sin credenciales"
            self._actualizar_ui_estado()
            self._programar_proxima_sincronizacion()
            return

        self.sync_en_progreso = True
        self.estado_conexion = "Conectando..."
        self._actualizar_ui_estado()
        self.log_ui("Iniciando sincronización...")

        try:
            user, pwd = cargar_credenciales(self._log)
            if not user or not pwd:
                self.estado_conexion = "Error: Credenciales inválidas"
                self.log_ui("Error: Credenciales inválidas.")
                self._log("[AUTH] Error de autenticación: credenciales inválidas.")  # RF-30
                return

            credenciales = Credenciales(usuario=user, password=pwd)
            servicio = ServicioNodo(credenciales, log_fn=self._log)
            resultado = servicio.sincronizar_pedidos()

            if resultado["exito"]:
                self.estado_conexion = "Conectado"
                self.ultima_sincronizacion = datetime.now()
                pedidos_desde_nodo = resultado["pedidos"] or []

                nuevos, modificados, nuevo_estado = \
                    self.gestor_estado.sincronizar_y_detectar_nuevos(pedidos_desde_nodo)

                self._actualizar_tabla(modificados, nuevo_estado, nuevos)

                # RF-13: no alertar en la primera sincronización
                if not self.primera_sincronizacion:
                    for pedido in nuevos:
                        self._generar_alerta_pedido_nuevo(pedido)
                        self._log(f"[NUEVO PEDIDO] {pedido.numero_pedido} - {pedido.vendedor} → {pedido.cliente}")  # RF-30
                else:
                    if nuevos:
                        self._log(f"[INFO] {len(nuevos)} pedido(s) nuevos encontrados al iniciar (sin alertas por RF-13).")

                self.gestor_estado.guardar_estado_actual()
                msg = f"Sincronización exitosa - {len(nuevos)} nuevo(s), {len(modificados)} modificado(s)"
                self.log_ui(msg)
                self._log(f"[SYNC] {msg}")  # RF-30

                if self.primera_sincronizacion:
                    self.primera_sincronizacion = False

            else:
                self.estado_conexion = "Error"
                self.log_ui(f"Error: {resultado['mensaje']}")
                self._log(f"[ERROR CONEXIÓN] {resultado['mensaje']}")  # RF-30

        except Exception as e:
            self.estado_conexion = "Error"
            self.log_ui(f"Error inesperado: {str(e)}")
            self._log(f"[ERROR] {str(e)}")  # RF-30
        finally:
            self.sync_en_progreso = False
            self._actualizar_ui_estado()
            self._programar_proxima_sincronizacion()  # RF-26: reprogramar siempre

    # ------------------------------------------------------------------
    # Tabla
    # ------------------------------------------------------------------
    def _actualizar_tabla(self, pedidos_modificados: list, todos: dict, nuevos: list):
        self.table_pedidos.clear()

        # Ordenar por fecha desc (RF-10) — funciona correctamente gracias a la
        # corrección en servicio_nodo.py que asigna fechas incrementales.
        pedidos_ordenados = sorted(todos.values(), key=lambda p: p.fecha, reverse=True)
        nuevos_numeros = {p.numero_pedido for p in nuevos}

        for pedido in pedidos_ordenados:
            monto = f"{int(pedido.total):,}".replace(",", ".")
            if pedido.moneda:
                monto += f" {pedido.moneda}"

            numero = pedido.numero_pedido
            if pedido.numero_pedido in nuevos_numeros:
                numero = f"{numero} [New]"

            self.table_pedidos.add_row([
                numero, pedido.vendedor, pedido.cliente, monto, pedido.estado
            ])

        self.lbl_pedidos_count.configure(text=f"{len(pedidos_ordenados)} pedidos")
        self.table_pedidos.scroll_to_top()

    # ------------------------------------------------------------------
    # Alertas (RF-14 – RF-20, RF-28)
    # ------------------------------------------------------------------
    def _generar_alerta_pedido_nuevo(self, pedido):
        def alertar():
            if self.check_sonido_var.get() == "on":
                alerta_sonora()
            if self.check_lectura_var.get() == "on":
                reproducir_texto(
                    f"El vendedor {pedido.vendedor} ha cargado un pedido para {pedido.cliente}"
                )

        threading.Thread(target=alertar, daemon=True).start()

    # ------------------------------------------------------------------
    # Estado UI
    # ------------------------------------------------------------------
    def _actualizar_ui_estado(self):
        self.lbl_estado_conexion.configure(text=f"Estado: {self.estado_conexion}")
        if self.ultima_sincronizacion:
            self.lbl_ultima_sync.configure(
                text=f"Última sincronización: "
                     f"{self.ultima_sincronizacion.strftime('%d/%m/%Y %H:%M:%S')}"
            )

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
        self.gestor_estado.guardar_estado_actual()
        self.destroy()
        sys.exit(0)
