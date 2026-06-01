import pandas as pd
from typing import List, Optional
from pathlib import Path
from core.modelos import Pedido
from datetime import datetime
import os
import sys

class RepositorioPedidos:
    """Gestiona la lectura y persistencia de pedidos desde Excel"""
    
    def __init__(self, ruta_archivo: str = "reporte_pedidos.xlsx"):
        self.ruta_archivo = Path(self._get_root_dir() / ruta_archivo)
        
    def _get_root_dir(self) -> Path:
        """Obtiene el directorio raíz del proyecto"""
        if getattr(sys, 'frozen', False):
            return Path(os.path.dirname(os.path.abspath(sys.executable)))
        return Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
    def cargar_pedidos(self) -> List[Pedido]:
        """Carga los pedidos desde el archivo Excel en orden inverso (nuevos primero)"""
        if not self.ruta_archivo.exists():
            return []
        
        df = pd.read_excel(self.ruta_archivo)
        pedidos = []
        
        for _, row in df.iterrows():
            pedido = Pedido(
                numero_pedido=str(row.get('Factura', '')),
                fecha=datetime.now(),
                estado=str(row.get('EstadoTransaccion', '')),
                total=float(row.get('Total', 0)) if pd.notna(row.get('Total')) else 0,
                cliente=str(row.get('Cliente', '')),
                vendedor=str(row.get('Vendedor', '')),
                moneda=str(row.get('Moneda', '')) if pd.notna(row.get('Moneda')) else ""
            )
            pedidos.append(pedido)
        
        # INVERTIR EL ORDEN: los pedidos más nuevos (últimos en el Excel) aparecerán primero
        pedidos.reverse()
        
        return pedidos
    
    def guardar_pedidos(self, pedidos: List[Pedido]) -> None:
        """Guarda los pedidos en el archivo Excel"""
        data = [p.to_dict() for p in pedidos]
        df = pd.DataFrame(data)
        df.to_excel(self.ruta_archivo, index=False)
    
    def existe_archivo(self) -> bool:
        """Verifica si el archivo existe"""
        return self.ruta_archivo.exists()