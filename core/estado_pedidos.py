# core/estado_pedidos.py
import json
import os
from typing import List, Dict, Tuple
from datetime import datetime
from .modelos import Pedido

ARCHIVO_ESTADO = "ultimo_estado_conocido.json"


class GestorEstadoPedidos:
    """Gestiona la persistencia y comparación de pedidos para detectar novedades."""

    def __init__(self, log_fn=None):
        self.log = log_fn or print
        self.estado_actual: Dict[str, Pedido] = {}
        self._cargar_estado_guardado()

    def _get_ruta_estado(self) -> str:
        app_dir = os.path.join(os.environ.get('APPDATA', '.'), 'PracticalPedidos')
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, ARCHIVO_ESTADO)

    def _cargar_estado_guardado(self):
        try:
            with open(self._get_ruta_estado(), 'r', encoding='utf-8') as f:
                datos_guardados = json.load(f)
                for num_pedido, datos in datos_guardados.items():
                    self.estado_actual[num_pedido] = Pedido(
                        numero_pedido=datos['numero_pedido'],
                        fecha=datetime.fromisoformat(datos['fecha']),
                        estado=datos['estado'],
                        total=datos['total'],
                        cliente=datos['cliente'],
                        vendedor=datos['vendedor'],
                        moneda=datos.get('moneda', ''),
                        observaciones=datos.get('observaciones'),
                    )
            self.log("[ESTADO] Estado previo cargado.")
        except FileNotFoundError:
            self.log("[ESTADO] No se encontró estado previo. Iniciando desde cero.")
        except Exception as e:
            self.log(f"[ESTADO] Error al cargar estado: {e}")

    def guardar_estado_actual(self):
        datos_a_guardar = {}
        for num_pedido, pedido in self.estado_actual.items():
            d = pedido.to_dict()
            d['fecha'] = pedido.fecha.isoformat()
            datos_a_guardar[num_pedido] = d

        try:
            with open(self._get_ruta_estado(), 'w', encoding='utf-8') as f:
                json.dump(datos_a_guardar, f, indent=4, ensure_ascii=False)
            self.log("[ESTADO] Estado actual guardado correctamente.")
        except Exception as e:
            self.log(f"[ESTADO] Error al guardar estado: {e}")

    def sincronizar_y_detectar_nuevos(
        self,
        pedidos_nuevos_desde_nodo: List[Pedido],
    ) -> Tuple[List[Pedido], List[Pedido], Dict[str, Pedido]]:
        """
        Compara la lista nueva con el estado actual.

        Retorna:
            nuevos_pedidos       – pedidos que no existían antes (para alertar).
            pedidos_modificados  – pedidos nuevos o con datos cambiados (para UI).
            nuevo_estado         – estado completo actualizado (todos los pedidos).
        """
        nuevos_pedidos: List[Pedido] = []
        pedidos_modificados: List[Pedido] = []
        cambios = {"actualizados": [], "eliminados": []}

        nuevo_estado: Dict[str, Pedido] = {}
        pedidos_nodos_dict = {p.numero_pedido: p for p in pedidos_nuevos_desde_nodo}

        for num_pedido, pedido_nuevo in pedidos_nodos_dict.items():
            es_nuevo = num_pedido not in self.estado_actual
            es_actualizacion = False

            if not es_nuevo:
                viejo = self.estado_actual[num_pedido]
                if (viejo.cliente  != pedido_nuevo.cliente  or
                    viejo.vendedor != pedido_nuevo.vendedor or
                    viejo.estado   != pedido_nuevo.estado   or
                    viejo.total    != pedido_nuevo.total):
                    es_actualizacion = True
                    cambios["actualizados"].append(num_pedido)

            if es_nuevo:
                nuevos_pedidos.append(pedido_nuevo)
                cambios["actualizados"].append(f"{num_pedido} (NUEVO)")

            if es_nuevo or es_actualizacion:
                pedidos_modificados.append(pedido_nuevo)

            nuevo_estado[num_pedido] = pedido_nuevo

        for num_pedido in self.estado_actual:
            if num_pedido not in pedidos_nodos_dict:
                cambios["eliminados"].append(num_pedido)

        if cambios["actualizados"]:
            self.log(f"[ESTADO] Cambios: {cambios['actualizados']}")
        if cambios["eliminados"]:
            self.log(f"[ESTADO] Eliminados: {cambios['eliminados']}")

        self.estado_actual = nuevo_estado
        return nuevos_pedidos, pedidos_modificados, nuevo_estado
