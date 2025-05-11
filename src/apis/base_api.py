# /src/apis/base_api.py

"""
Clase base para todos los clientes de API de empleo.
Establece métodos comunes como carga de API keys, nombre de fuente y estructuras estándar.
"""

import os
import logging
from typing import Dict, Any, Optional, Protocol

class HTTPClientProtocol(Protocol):
    def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        ...
    def __init__(self, source_name: str, http_client: HTTPClientProtocol, config: Optional[Dict[str, Any]] = None):
        ...

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class BaseAPIClient:
    def __init__(self, source_name: str, http_client: Any, config: Optional[Dict[str, Any]] = None):
        """
        Clase base para clientes API. Define fuente, configuración y cliente HTTP.

        Args:
            source_name (str): Nombre de la fuente (ej. 'adzuna', 'jooble')
            http_client (Any): Cliente HTTP para realizar peticiones (generalmente requests session con wrapper)
            config (Optional[Dict[str, Any]]): Configuración específica del cliente
        """
        self.source_name = source_name
        self.http_client = http_client
        self.config = config or {}

    def _get_api_key(self, suffix: str = "_API_KEY", default: Optional[str] = None) -> Optional[str]:
        """
        Obtiene una clave API desde variables de entorno. Usa el nombre de fuente en mayúsculas + sufijo.
        """
        key_name = f"{self.source_name.upper()}{suffix}"
        api_key = os.environ.get(key_name, default)
        if not api_key:
            logger.warning(f"[{self.source_name}] Variable de entorno {key_name} no encontrada.")
        return api_key

    def get_standard_job_dict(self) -> Dict[str, Any]:
        """
        Devuelve un diccionario estándar vacío para representar una oferta de trabajo normalizada.
        """
        return {
            "titulo": None,
            "empresa": None,
            "ubicacion": None,
            "fecha_publicacion": None,
            "url": None,
            "descripcion": None,
            "salario": None
        }
