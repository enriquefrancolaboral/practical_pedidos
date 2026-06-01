from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class Pedido:
    """Entidad de dominio que representa un pedido"""
    numero_pedido: str
    fecha: datetime
    estado: str
    total: float
    cliente: str
    vendedor: str = ""
    moneda: str = ""
    observaciones: Optional[str] = None
    
    def es_entregable(self) -> bool:
        """Regla de negocio: determinar si el pedido puede ser entregado"""
        return self.estado.lower() == 'pendiente'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario para facilitar la serialización"""
        return {
            'numero_pedido': self.numero_pedido,
            'fecha': self.fecha.strftime('%Y-%m-%d %H:%M:%S'),
            'estado': self.estado,
            'total': self.total,
            'cliente': self.cliente,
            'vendedor': self.vendedor,
            'moneda': self.moneda,
            'observaciones': self.observaciones
        }

@dataclass
class Credenciales:
    """Entidad de dominio para credenciales del sistema NODO"""
    usuario: str
    password: str
    servidor: str = "https://nodo-practical.nodosolutions.com"