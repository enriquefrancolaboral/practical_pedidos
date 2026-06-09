# presentation/ventanas/credenciales.py
import customtkinter as ctk
from utils.credentials import guardar_credenciales
from core.modelos import Credenciales
from data.servicio_nodo import ServicioNodo
from playwright.sync_api import sync_playwright
import sys
import os
import threading
from utils.path_utils import resource_path

COLOR_PANEL = "#13132b"
COLOR_ACCENT = "#1a1a40"
COLOR_BORDER = "#2a2a55"
COLOR_BTN_CONFIG = "#2d4a22"
COLOR_BTN_CONFIG_HOV = "#3a6b2a"
COLOR_BTN_PRIMARY = "#1a56db"
COLOR_BTN_PRIMARY_HOV = "#1e6ef5"
COLOR_TEXT = "#e8eaf6"
COLOR_TEXT_DIM = "#8892a4"
COLOR_ERROR = "#f56565"
COLOR_SUCCESS = "#48bb78"
FONT_APP_TITLE = ("Segoe UI", 15, "bold")
FONT_SECTION = ("Segoe UI", 10, "bold")
FONT_BTN = ("Segoe UI", 11, "bold")

class VentanaCredenciales(ctk.CTkToplevel):
    def __init__(self, parent, on_guardado=None):
        super().__init__(parent)
        self.title("Configurar Credenciales NODO")
        self.geometry("440x380")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_PANEL)
        self.on_guardado = on_guardado
        self.parent = parent
        
        # Cargar icono desde la carpeta assets
        try:
            icon_path = resource_path(os.path.join("presentation", "assets", "icono.ico"))
            if os.path.exists(icon_path):
                self.after(200, lambda: self.iconbitmap(icon_path))
            else:
                print(f"Icono no encontrado en: {icon_path}")
        except Exception as e:
            print(f"No se pudo cargar el icono de la ventana: {e}")
        
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
        
        # Campo Usuario
        ctk.CTkLabel(f, text="NODO — Usuario (email)",
                     font=FONT_SECTION, text_color=COLOR_TEXT_DIM
                     ).pack(padx=28, pady=(0, 2), anchor="w")
        self.entry_nodo_user = ctk.CTkEntry(f, width=384, placeholder_text="usuario@ejemplo.com")
        self.entry_nodo_user.pack(padx=28, pady=(0, 10))
        
        # Campo Contraseña
        ctk.CTkLabel(f, text="NODO — Contraseña",
                     font=FONT_SECTION, text_color=COLOR_TEXT_DIM
                     ).pack(padx=28, pady=(0, 2), anchor="w")
        self._campo_password(f, "entry_nodo_pass", "••••••••", pady_bottom=18)
        
        # Etiqueta de mensajes (error/success)
        self.lbl_mensaje = ctk.CTkLabel(f, text=" ", font=("Segoe UI", 10), text_color=COLOR_ERROR, height=40)
        self.lbl_mensaje.pack(padx=28, pady=(0, 4))
        
        # Botones
        btn_frame = ctk.CTkFrame(f, fg_color="transparent")
        btn_frame.pack(fill="x", padx=28, pady=(0, 18))
        
        # Botón Probar Conexión (RF-02)
        self.btn_probar = ctk.CTkButton(
            btn_frame, text="🔌  Probar Conexión",
            font=FONT_BTN, fg_color=COLOR_ACCENT, hover_color=COLOR_BORDER,
            corner_radius=7, height=38, command=self._probar_conexion
        )
        self.btn_probar.pack(side="left", padx=(0, 10), fill="x", expand=True)
        
        # Botón Guardar
        self.btn_guardar = ctk.CTkButton(
            btn_frame, text="🔒  Guardar de forma segura",
            font=FONT_BTN, fg_color=COLOR_BTN_CONFIG, hover_color=COLOR_BTN_CONFIG_HOV,
            corner_radius=7, height=38, command=self._guardar
        )
        self.btn_guardar.pack(side="left", fill="x", expand=True)
        
        self.update_idletasks()
        self.focus_force()
        self.grab_set()
        self.lift()
    
    def _probar_conexion(self):
        """Prueba de conexión a NODO con las credenciales ingresadas (RF-02)"""
        usuario = self.entry_nodo_user.get().strip()
        password = self.entry_nodo_pass.get().strip()
        
        if not all([usuario, password]):
            self._mostrar_mensaje("Todos los campos son obligatorios.", COLOR_ERROR)
            return
        
        # Deshabilitar botones durante la prueba
        self.btn_probar.configure(state="disabled", text="⏳ Probando...")
        self.btn_guardar.configure(state="disabled")
        
        # Ejecutar prueba en hilo separado para no bloquear la UI
        def prueba():
            try:
                credenciales = Credenciales(usuario=usuario, password=password)
                servicio = ServicioNodo(credenciales, log_fn=print)
                
                # Realizar prueba de conexión
                resultado = servicio.probar_conexion()
                
                # Actualizar UI en el hilo principal
                self.after(0, lambda: self._resultado_prueba(resultado))
                
            except Exception as e:
                self.after(0, lambda: self._resultado_prueba({"exito": False, "mensaje": f"Error: {str(e)}"}))
        
        threading.Thread(target=prueba, daemon=True).start()
    
    def _resultado_prueba(self, resultado):
        """Procesa el resultado de la prueba de conexión"""
        # Re-habilitar botones
        self.btn_probar.configure(state="normal", text="🔌  Probar Conexión")
        self.btn_guardar.configure(state="normal")
        
        if resultado["exito"]:
            self._mostrar_mensaje("✅ Conexión exitosa! Las credenciales son correctas.", COLOR_SUCCESS)
        else:
            self._mostrar_mensaje(f"❌ Error de conexión: {resultado['mensaje']}", COLOR_ERROR)
    
    def _guardar(self):
        """Guarda las credenciales después de validarlas (RF-02, RF-03)"""
        usuario = self.entry_nodo_user.get().strip()
        password = self.entry_nodo_pass.get().strip()
        
        if not all([usuario, password]):
            self._mostrar_mensaje("Todos los campos son obligatorios.", COLOR_ERROR)
            return
        
        # Mostrar mensaje de validación
        self._mostrar_mensaje("🔍 Validando credenciales...", COLOR_TEXT_DIM)
        self.btn_guardar.configure(state="disabled", text="⏳ Validando...")
        self.btn_probar.configure(state="disabled")
        
        # Ejecutar validación en hilo separado
        def validar_y_guardar():
            try:
                # Primero probar la conexión (RF-02)
                credenciales = Credenciales(usuario=usuario, password=password)
                servicio = ServicioNodo(credenciales, log_fn=print)
                
                resultado_prueba = servicio.probar_conexion()
                
                if not resultado_prueba["exito"]:
                    # Credenciales inválidas (RF-03)
                    self.after(0, lambda: self._mostrar_mensaje(
                        f"❌ Credenciales inválidas: {resultado_prueba['mensaje']}", 
                        COLOR_ERROR
                    ))
                    self.after(0, self._habilitar_botones)
                    return
                
                # Credenciales válidas, guardar (RF-04)
                ok = guardar_credenciales(usuario, password)
                
                if ok:
                    self.after(0, lambda: self._mostrar_mensaje(
                        "✅ Credenciales guardadas correctamente!", 
                        COLOR_SUCCESS
                    ))
                    self.after(1000, self._cerrar_con_exito)
                else:
                    self.after(0, lambda: self._mostrar_mensaje(
                        "❌ Error al guardar. Verifica permisos del sistema.", 
                        COLOR_ERROR
                    ))
                    self.after(0, self._habilitar_botones)
                    
            except Exception as e:
                self.after(0, lambda: self._mostrar_mensaje(
                    f"❌ Error inesperado: {str(e)}", 
                    COLOR_ERROR
                ))
                self.after(0, self._habilitar_botones)
        
        threading.Thread(target=validar_y_guardar, daemon=True).start()
    
    def _mostrar_mensaje(self, mensaje, color):
        """Muestra un mensaje en la etiqueta correspondiente"""
        self.lbl_mensaje.configure(text=mensaje, text_color=color)
        # Limpiar mensaje después de 5 segundos si es éxito o error
        if color != COLOR_TEXT_DIM:
            self.after(5000, lambda: self.lbl_mensaje.configure(text=" "))
    
    def _habilitar_botones(self):
        """Re-habilita los botones después de una operación"""
        self.btn_guardar.configure(state="normal", text="🔒  Guardar de forma segura")
        self.btn_probar.configure(state="normal", text="🔌  Probar Conexión")
    
    def _cerrar_con_exito(self):
        """Cierra la ventana después de guardar exitosamente"""
        if self.on_guardado:
            self.on_guardado()
        self.destroy()
    
    def _cerrar(self):
        """Cierra la ventana sin guardar"""
        self.destroy()