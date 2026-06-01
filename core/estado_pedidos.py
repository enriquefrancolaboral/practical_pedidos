# core/estado_pedidos.py
import json
import os
from typing import List, Dict, Set, Tuple
from datetime import datetime
from .modelos import Pedido

# Usaremos un archivo JSON simple para persistir el estado conocido entre sesiones
ARCHIVO_ESTADO = "ultimo_estado_conocido.json"

class GestorEstadoPedidos:
    """Gestiona la persistencia y comparación de pedidos para detectar novedades."""

    def __init__(self, log_fn=None):
        self.log = log_fn or print
        self.estado_actual: Dict[str, Pedido] = {}  # Mapa: numero_pedido -> Pedido
        self._cargar_estado_guardado()

    def _get_ruta_estado(self) -> str:
        """Obtiene la ruta al archivo de estado en el directorio del usuario."""
        # Ideal: Guardar en %APPDATA%/PracticalPedidos/
        app_dir = os.path.join(os.environ.get('APPDATA', '.'), 'PracticalPedidos')
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, ARCHIVO_ESTADO)

    def _cargar_estado_guardado(self):
        """Carga el estado de pedidos desde el archivo JSON al iniciar."""
        try:
            with open(self._get_ruta_estado(), 'r', encoding='utf-8') as f:
                datos_guardados = json.load(f)
                for num_pedido, datos in datos_guardados.items():
                    # Reconstruir el objeto Pedido desde el diccionario
                    self.estado_actual[num_pedido] = Pedido(
                        numero_pedido=datos['numero_pedido'],
                        fecha=datetime.fromisoformat(datos['fecha']),
                        estado=datos['estado'],
                        total=datos['total'],
                        cliente=datos['cliente'],
                        vendedor=datos['vendedor'],
                        moneda=datos.get('moneda', ''),
                        observaciones=datos.get('observaciones')
                    )
            self.log("[ESTADO] Estado previo cargado.")
        except FileNotFoundError:
            self.log("[ESTADO] No se encontró estado previo. Iniciando desde cero.")
        except Exception as e:
            self.log(f"[ESTADO] Error al cargar estado: {e}")

    def guardar_estado_actual(self):
        """Guarda el estado actual de pedidos en el archivo JSON."""
        datos_a_guardar = {}
        for num_pedido, pedido in self.estado_actual.items():
            datos_a_guardar[num_pedido] = pedido.to_dict()
            # Asegurar que la fecha sea ISO string para serialización
            datos_a_guardar[num_pedido]['fecha'] = pedido.fecha.isoformat()

        try:
            with open(self._get_ruta_estado(), 'w', encoding='utf-8') as f:
                json.dump(datos_a_guardar, f, indent=4, ensure_ascii=False)
            self.log("[ESTADO] Estado actual guardado correctamente.")
        except Exception as e:
            self.log(f"[ESTADO] Error al guardar estado: {e}")

    def sincronizar_y_detectar_nuevos(self, pedidos_nuevos_desde_nodo: List[Pedido]) -> Tuple[List[Pedido], List[Pedido], Dict[str, Dict]]:
        """
        Compara la lista nueva con el estado actual.
        Retorna:
        - Lista de pedidos nuevos (para alertar).
        - Lista de pedidos actualizados/eliminados (para refrescar UI).
        - El nuevo estado actualizado.
        """
        nuevos_pedidos: List[Pedido] = []
        pedidos_actualizados_o_nuevos: List[Pedido] = []  # Todo lo que va a la UI
        cambios = {"actualizados": [], "eliminados": []}  # Para log

        nuevo_estado: Dict[str, Pedido] = {}
        pedidos_nodos_dict = {p.numero_pedido: p for p in pedidos_nuevos_desde_nodo}

        # 1. Detectar pedidos nuevos o actualizados
        for num_pedido, pedido_nuevo in pedidos_nodos_dict.items():
            es_nuevo = num_pedido not in self.estado_actual
            es_actualizacion = False

            if not es_nuevo:
                pedido_viejo = self.estado_actual[num_pedido]
                # Comparar campos importantes para ver si hubo cambio (Cliente, Vendedor, Estado, Total)
                if (pedido_viejo.cliente != pedido_nuevo.cliente or
                    pedido_viejo.vendedor != pedido_nuevo.vendedor or
                    pedido_viejo.estado != pedido_nuevo.estado or
                    pedido_viejo.total != pedido_nuevo.total):
                    es_actualizacion = True
                    cambios["actualizados"].append(num_pedido)

            if es_nuevo:
                nuevos_pedidos.append(pedido_nuevo)
                cambios["actualizados"].append(f"{num_pedido} (NUEVO)")

            if es_nuevo or es_actualizacion:
                pedidos_actualizados_o_nuevos.append(pedido_nuevo)

            nuevo_estado[num_pedido] = pedido_nuevo

        # 2. Detectar pedidos eliminados en el nuevo reporte
        for num_pedido, pedido_viejo in self.estado_actual.items():
            if num_pedido not in pedidos_nodos_dict:
                cambios["eliminados"].append(num_pedido)
                # No lo agregamos a nuevo_estado, por lo tanto se "elimina"

        # Registrar cambios
        if cambios["actualizados"]:
            self.log(f"[ESTADO] Cambios detectados: {cambios['actualizados']}")
        if cambios["eliminados"]:
            self.log(f"[ESTADO] Pedidos eliminados: {cambios['eliminados']}")

        # Actualizar el estado interno
        self.estado_actual = nuevo_estado

        # Devolver: nuevos, todos los que van a UI (nuevos+actualizados), y el nuevo estado completo
        return nuevos_pedidos, pedidos_actualizados_o_nuevos, nuevo_estado