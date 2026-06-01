#!/usr/bin/env python
# app.py - Aplicación principal

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import queue
import threading
import pandas as pd
import os
import sys
import time
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

# Colores
COLOR_BG = "#0e0e1a"
COLOR_PANEL = "#13132b"
COLOR_ACCENT = "#1a1a40"
COLOR_BORDER = "#2a2a55"
COLOR_BTN_BLUE = "#1a56db"
COLOR_BTN_HOVER = "#1e6ef5"
COLOR_BTN_STOP = "#c0392b"
COLOR_BTN_STOP_HOVER = "#e74c3c"
COLOR_BTN_CONFIG = "#2d4a22"
COLOR_BTN_CONFIG_HOV = "#3a6b2a"
COLOR_TEXT = "#e8eaf6"
COLOR_TEXT_DIM = "#8892a4"
FONT_APP_TITLE = ("Segoe UI", 15, "bold")
FONT_LABEL = ("Segoe UI", 11)
FONT_BTN = ("Segoe UI", 11, "bold")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.title("PRACTICAL PEDIDOS")
        
        # Cargar icono
        try:
            icon_path = resource_path(os.path.join("presentation", "assets", "icono.ico"))
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
            else:
                print(f"Icono no encontrado en: {icon_path}")
        except Exception as e:
            print(f"No se pudo cargar el icono: {e}")
        
        self.geometry("1200x750")
        self.minsize(900, 600)
        self.configure(fg_color=COLOR_BG)
        
        # Inicializar componentes
        self.repositorio = RepositorioPedidos()  # Ya no se usará para cargar desde archivo fijo
        self.gestor_estado = GestorEstadoPedidos(log_fn=print)
        self.sync_en_progreso = False
        self.timer_proximo = None  # Para el Timer de la próxima sincronización
        self.ultima_sincronizacion: datetime = None
        self.primera_sincronizacion = True  # Para controlar alertas al inicio (RF-13)
        
        self._build_ui()
        self._verificar_credenciales()
        
        # Iniciar la primera sincronización inmediatamente (RF-08)
        self.after(500, self._ejecutar_sincronizacion)  # Pequeño delay para que la UI cargue
        
        # Configurar cierre seguro
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
    
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
        
        # Título
        ctk.CTkLabel(left, text="P E D I D O S", font=FONT_APP_TITLE, text_color=COLOR_TEXT
                    ).pack(padx=18, pady=(22, 2), anchor="w")
        
        ctk.CTkLabel(left, text="Alerta de nuevos pedidos en NODO", font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM
                    ).pack(padx=18, pady=(0, 24), anchor="w")
        
        # Checkboxes de configuración de alertas
        self.check_sonido_var = ctk.StringVar(value="off")
        self.check_sonido = ctk.CTkCheckBox(
            left, text="Sonido de notificación", font=FONT_LABEL, text_color=COLOR_TEXT,
            variable=self.check_sonido_var, onvalue="on", offvalue="off",
            command=self._on_check_sonido
        )
        self.check_sonido.pack(padx=18, pady=(0, 16), anchor="w")
        
        self.check_lectura_var = ctk.StringVar(value="off")
        self.check_lectura = ctk.CTkCheckBox(
            left, text="Lectura de mensajes", font=FONT_LABEL, text_color=COLOR_TEXT,
            variable=self.check_lectura_var, onvalue="on", offvalue="off",
            command=self._on_check_lectura
        )
        self.check_lectura.pack(padx=18, pady=(0, 24), anchor="w")
        
        # Información de estado
        self.lbl_estado_conexion = ctk.CTkLabel(
            left, text="Estado: Desconectado", 
            font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM
        )
        self.lbl_estado_conexion.pack(padx=18, pady=(0, 5), anchor="w")
        
        self.lbl_ultima_sync = ctk.CTkLabel(
            left, text="Última sincronización: --:--:--", 
            font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM
        )
        self.lbl_ultima_sync.pack(padx=18, pady=(0, 20), anchor="w")
        
        # Botón de configuración
        self.btn_config = ctk.CTkButton(
            left, text="🔧  Configurar Credenciales", font=FONT_BTN,
            fg_color=COLOR_BTN_CONFIG, hover_color=COLOR_BTN_CONFIG_HOV,
            corner_radius=7, height=40, command=self._on_config_credenciales
        )
        self.btn_config.pack(side="bottom", fill="x", padx=18, pady=(0, 15))
        
        # Footer
        self.lbl_footer = ctk.CTkLabel(
            left, text="Listo.", font=("Segoe UI", 10), text_color=COLOR_TEXT_DIM
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
        
        ctk.CTkLabel(header_frame, text="LISTADO DE PEDIDOS", font=("Segoe UI", 20, "bold"), text_color=COLOR_TEXT
                    ).grid(row=0, column=0, sticky="w")
        
        self.lbl_pedidos_count = ctk.CTkLabel(header_frame, text="0 pedidos", font=("Segoe UI", 12), text_color=COLOR_TEXT_DIM)
        self.lbl_pedidos_count.grid(row=0, column=1, sticky="e")
        
        self.table_pedidos = ModernTable(right, headers=["#", "Vendedor", "Cliente", "Monto", "Estado"])
        self.table_pedidos.grid(row=1, column=0, sticky="nsew")
    
    def _on_check_sonido(self):
        """Callback cuando se marca/desmarca el checkbox de sonido"""
        if self.check_sonido_var.get() == "on":
            print("✅ Sonido activado - Reproduciendo prueba...")
            import winsound
            winsound.Beep(1000, 200)
            winsound.Beep(1200, 200)
        else:
            print("🔇 Sonido desactivado")
    
    def _on_check_lectura(self):
        """Callback cuando se marca/desmarca el checkbox de lectura"""
        if self.check_lectura_var.get() == "on":
            print("🔊 Lectura activada - Probando TTS...")
            reproducir_texto("La lectura de mensajes está activada")
        else:
            print("🔇 Lectura desactivada")
    
    def _on_config_credenciales(self):
        VentanaCredenciales(self, on_guardado=self._on_credenciales_guardadas)
    
    def _on_credenciales_guardadas(self):
        self.lbl_footer.configure(text="Credenciales guardadas correctamente.")
        # Forzar una sincronización inmediata después de guardar credenciales
        self.after(1000, self._ejecutar_sincronizacion)
    
    def _programar_proxima_sincronizacion(self):
        """Calcula y programa la próxima sincronización a los próximos 5 minutos exactos (RF-07)"""
        ahora = datetime.now()
        # Calcular minutos hasta el próximo múltiplo de 5
        minutos_actual = ahora.minute
        minutos_faltantes = (5 - (minutos_actual % 5)) % 5
        if minutos_faltantes == 0 and ahora.second == 0:
            # Ya estamos exactamente en un minuto múltiplo de 5, programar para 5 minutos después
            minutos_faltantes = 5
        
        segundos_faltantes = minutos_faltantes * 60 - ahora.second
        if segundos_faltantes <= 0:
            segundos_faltantes += 300  # Por si acaso, programar a 5 minutos
        
        self.log_ui(f"Próxima sincronización programada en {segundos_faltantes} segundos.")
        # Usar Timer de threading para ejecutar en otro hilo
        self.timer_proximo = Timer(segundos_faltantes, self._ejecutar_sincronizacion_en_hilo)
        self.timer_proximo.daemon = True
        self.timer_proximo.start()
    
    def _ejecutar_sincronizacion_en_hilo(self):
        """Lanza la sincronización en un hilo separado para no bloquear la UI"""
        if self.sync_en_progreso:
            print("Sincronización previa en progreso. Omitiendo...")
            self._programar_proxima_sincronizacion()  # Reprogramar
            return
        self.after(0, self._ejecutar_sincronizacion)  # Ejecutar en el hilo principal de Tk
    
    def _ejecutar_sincronizacion(self):
        """Lógica principal de sincronización (ejecutada en el hilo principal de Tk)"""
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
            user, pwd = cargar_credenciales(print)
            if not user or not pwd:
                self.estado_conexion = "Error: Credenciales inválidas"
                self.log_ui("Error: Credenciales inválidas")
                return
            
            credenciales = Credenciales(usuario=user, password=pwd)
            servicio = ServicioNodo(credenciales, log_fn=print)
            
            resultado = servicio.sincronizar_pedidos()
            
            if resultado["exito"]:
                self.estado_conexion = "Conectado"
                self.ultima_sincronizacion = datetime.now()
                pedidos_nuevos_desde_nodo = resultado["pedidos"]
                
                # Verificar que hay pedidos
                if pedidos_nuevos_desde_nodo is None:
                    pedidos_nuevos_desde_nodo = []
                
                # Sincronizar con el gestor de estado para detectar nuevos
                nuevos_pedidos, pedidos_actualizados, nuevo_estado = self.gestor_estado.sincronizar_y_detectar_nuevos(pedidos_nuevos_desde_nodo)
                
                # Actualizar la tabla en la UI con todos los pedidos
                self._actualizar_tabla(pedidos_actualizados, nuevo_estado, nuevos_pedidos)
                
                # Generar alertas individuales para los pedidos NUEVOS (RF-14, RF-17)
                # RF-13: No alertar en la primera sincronización al abrir la app
                if not self.primera_sincronizacion:
                    for pedido_nuevo in nuevos_pedidos:
                        self._generar_alerta_pedido_nuevo(pedido_nuevo)
                else:
                    if nuevos_pedidos:
                        self.log_ui(f"Se encontraron {len(nuevos_pedidos)} pedido(s) nuevo(s), pero no se generan alertas por ser la primera ejecución.")
                
                # Guardar el estado actual para la próxima vez que se abra la app (RF-32)
                self.gestor_estado.guardar_estado_actual()
                
                self.log_ui(f"Sincronización exitosa - {len(nuevos_pedidos)} pedido(s) nuevo(s), {len(pedidos_actualizados)} actualizado(s)")
                
                # Marcar que ya no es la primera sincronización
                if self.primera_sincronizacion:
                    self.primera_sincronizacion = False
                
            else:
                self.estado_conexion = "Error"
                self.log_ui(f"Error: {resultado['mensaje']}")
                
        except Exception as e:
            self.estado_conexion = "Error"
            self.log_ui(f"Error inesperado: {str(e)}")
            print(f"Error en sincronización: {e}")
        finally:
            self.sync_en_progreso = False
            self._actualizar_ui_estado()
            # Programar la próxima sincronización, incluso si esta falló (RF-26)
            self._programar_proxima_sincronizacion()
    
    def _actualizar_tabla(self, pedidos_a_mostrar: list, todos_los_pedidos: dict, nuevos: list):
        """
        Actualiza la ModernTable con la información más reciente y marca los nuevos.
        
        Args:
            pedidos_a_mostrar: Lista de pedidos que cambiaron (nuevos o actualizados)
            todos_los_pedidos: Diccionario con todos los pedidos del estado actual
            nuevos: Lista de pedidos que son nuevos en esta sincronización
        """
        self.table_pedidos.clear()
        
        # Ordenar: Queremos los más recientes primero usando la fecha del pedido
        if todos_los_pedidos:
            pedidos_ordenados = sorted(todos_los_pedidos.values(), key=lambda p: p.fecha, reverse=True)
        else:
            pedidos_ordenados = []
        
        nuevos_numeros = {p.numero_pedido for p in nuevos}
        
        for pedido in pedidos_ordenados:
            # Formatear monto
            if pedido.moneda:
                monto = f"{int(pedido.total):,}".replace(",", ".") + f" {pedido.moneda}"
            else:
                monto = f"{int(pedido.total):,}".replace(",", ".")
            
            # Añadir [New] si es nuevo en esta sincronización (RF-12)
            # La etiqueta [New] se muestra hasta la próxima sincronización (RF-25)
            numero_mostrar = pedido.numero_pedido
            if pedido.numero_pedido in nuevos_numeros:
                numero_mostrar = f"{pedido.numero_pedido} [New]"
            
            self.table_pedidos.add_row([
                numero_mostrar,
                pedido.vendedor,
                pedido.cliente,
                monto,
                pedido.estado
            ])
        
        self.lbl_pedidos_count.configure(text=f"{len(pedidos_ordenados)} pedidos")
        self.table_pedidos.scroll_to_top()
    
    def _generar_alerta_pedido_nuevo(self, pedido):
        """Genera la alerta sonora y/o de voz para un pedido nuevo (RF-15, RF-16)"""
        # Ejecutar en un hilo separado para no bloquear la UI
        def alertar():
            # Sonido (RF-18)
            if self.check_sonido_var.get() == "on":
                alerta_sonora()
            
            # Voz (RF-19)
            if self.check_lectura_var.get() == "on":
                mensaje = f"El vendedor {pedido.vendedor} ha cargado un pedido para {pedido.cliente}"
                reproducir_texto(mensaje)
        
        threading.Thread(target=alertar, daemon=True).start()
    
    def _actualizar_ui_estado(self):
        """Actualiza las etiquetas de estado en la UI desde el hilo principal"""
        self.lbl_estado_conexion.configure(text=f"Estado: {self.estado_conexion}")
        if self.ultima_sincronizacion:
            self.lbl_ultima_sync.configure(
                text=f"Última sincronización: {self.ultima_sincronizacion.strftime('%d/%m/%Y %H:%M:%S')}"
            )
        else:
            self.lbl_ultima_sync.configure(text="Última sincronización: --")
    
    def log_ui(self, mensaje):
        """Muestra un mensaje en el footer de la UI de forma segura"""
        self.after(0, lambda: self.lbl_footer.configure(text=mensaje))
        print(mensaje)  # También imprimir en consola para debug
    
    def on_closing(self):
        """Maneja el cierre seguro de la aplicación (RF-31)"""
        print("Cerrando aplicación...")
        
        # Detener el timer de sincronización
        if self.timer_proximo:
            self.timer_proximo.cancel()
        
        # Guardar el estado actual de pedidos (RF-32)
        self.gestor_estado.guardar_estado_actual()
        
        # Destruir la ventana y salir
        self.destroy()
        sys.exit(0)