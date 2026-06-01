# utils/logger.py
import logging
import os

_logger = None

def get_logger() -> logging.Logger:
    global _logger
    if _logger:
        return _logger

    app_dir = os.path.join(os.environ.get('APPDATA', '.'), 'PracticalPedidos')
    os.makedirs(app_dir, exist_ok=True)
    log_path = os.path.join(app_dir, 'practical_pedidos.log')

    _logger = logging.getLogger('PracticalPedidos')
    _logger.setLevel(logging.INFO)

    if not _logger.handlers:
        fh = logging.FileHandler(log_path, encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s',
                                          datefmt='%Y-%m-%d %H:%M:%S'))
        _logger.addHandler(fh)

    return _logger


def log(mensaje: str):
    """Shortcut: escribe en archivo y en consola."""
    get_logger().info(mensaje)
    print(mensaje)
