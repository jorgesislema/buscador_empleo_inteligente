# -*- coding: utf-8 -*-
# /src/apis/base_api.py

"""
Plantilla Base para los Clientes de API de Empleo.

Aquí definimos la estructura común que seguirán todos nuestros clientes
que interactúan con APIs externas (Adzuna, Arbeitnow, Jobicy, etc.).
Usamos una Clase Base Abstracta (ABC) para asegurarnos de que todos
implementen la funcionalidad esencial de la misma manera.

La idea principal es que cada cliente específico (ej: AdzunaClient)
herede de BaseAPIClient e implemente el método abstracto 'fetch_jobs'.
"""

import abc      # Necesitamos esto para crear Clases Base Abstractas (ABC).
import logging  # Para registrar información desde la clase base o las hijas.
from typing import List, Dict, Any, Optional # ¡Nuestros queridos type hints!

# Importamos nuestro cliente HTTP. Lo recibiremos ya inicializado.
from src.utils.http_client import HTTPClient
# Importamos nuestro cargador de secretos (aunque lo usará más la clase hija).
from src.utils import config_loader

# Obtenemos un logger para este módulo base.
logger = logging.getLogger(__name__)

# --- Definición de la Clase Base Abstracta ---

class BaseAPIClient(abc.ABC):
    """
    Clase Base Abstracta para todos los clientes de API de empleo.

    Define la interfaz común y provee funcionalidades básicas.
    Cada cliente específico debe heredar de esta clase e implementar
    el método abstracto `Workspace_jobs`.

    Atributos:
        source_name (str): Nombre identificador de la fuente (ej: 'adzuna').
        http_client (HTTPClient): Instancia del cliente HTTP para hacer peticiones.
        config (dict): (Opcional) Configuración específica de la fuente leída de settings.yaml.
    """

    def __init__(self, source_name: str, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador de la clase base.

        Args:
            source_name (str): El nombre único de esta fuente API (ej: "adzuna").
                               Debería coincidir con la clave en settings.yaml -> sources -> apis.
            http_client (HTTPClient): Una instancia ya inicializada de nuestro cliente HTTP.
                                      ¡Se la pasamos desde fuera (inyección de dependencias)!
            config (Optional[Dict[str, Any]]): Un diccionario con la configuración específica
                                                para esta fuente, tal como aparece en settings.yaml
                                                (ej: {'enabled': True, 'results_per_page': 50}). Defaults to None.
        """
        self.source_name = source_name
        self.http_client = http_client
        # Guardamos la configuración específica por si la necesitamos (ej: results_per_page).
        # Si no se pasa config, guardamos un diccionario vacío para evitar errores al accederla.
        self.config = config if config is not None else {}
        logger.info(f"Inicializando cliente base para la fuente API: '{self.source_name}'")
        if not isinstance(http_client, HTTPClient):
            # Una pequeña comprobación por si acaso nos pasan algo que no es nuestro cliente HTTP.
            logger.error("¡Se esperaba una instancia de HTTPClient pero se recibió algo diferente!")
            raise TypeError("El argumento http_client debe ser una instancia de HTTPClient.")


    @abc.abstractmethod
    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Método abstracto para obtener ofertas de empleo de la API específica.

        **¡Cada clase hija DEBE implementar este método!**

        Debe encargarse de:
        1. Construir la(s) URL(s) de la API con los parámetros de búsqueda.
        2. (Opcional) Obtener la API key necesaria usando `_get_api_key()` o `config_loader.get_secret()`.
        3. Realizar la(s) petición(es) HTTP usando `self.http_client.get()`.
        4. Manejar la respuesta de la API (parsear JSON, verificar errores específicos de la API).
        5. **Normalizar** los datos obtenidos al formato estándar esperado.
        6. Devolver una lista de diccionarios, donde cada diccionario representa una oferta
           de empleo con claves estándar. Devolver una lista vacía si no hay resultados o hay error.

        Args:
            search_params (Dict[str, Any]): Un diccionario con los parámetros de búsqueda
                                           (ej: {'keywords': ['python', 'data'], 'location': 'Quito'}).
                                           La estructura exacta puede variar según lo que necesite la API.

        Returns:
            List[Dict[str, Any]]: Una lista de diccionarios. Cada diccionario es una oferta
                                  con claves estándar como: 'titulo', 'empresa', 'ubicacion',
                                  'descripcion', 'fecha_publicacion', 'url', 'fuente'.
                                  Es responsabilidad de la clase hija asegurar este formato.
        """
        # Como es abstracto, no ponemos código aquí, solo 'pass' o 'raise NotImplementedError'.
        # Las clases hijas se encargarán de poner la lógica real.
        raise NotImplementedError("¡Oops! La clase hija olvidó implementar fetch_jobs.")


    # --- Métodos de Ayuda (Opcionales pero Útiles) ---

    def _get_api_key(self, key_name_suffix: str = "_API_KEY") -> Optional[str]:
        """
        Método de ayuda para obtener la API key desde las variables de entorno.

        Construye el nombre esperado de la variable de entorno basado en el
        nombre de la fuente (ej: 'ADZUNA_API_KEY') y la obtiene usando config_loader.

        Args:
            key_name_suffix (str): El sufijo común para las claves API en el archivo .env.
                                   Defaults to "_API_KEY". Se pueden añadir otros como "_APP_ID", "_APP_KEY".

        Returns:
            Optional[str]: La clave API si se encuentra, o None si no.
        """
        # Construimos el nombre de la variable, ej: "ADZUNA" + "_API_KEY"
        env_var_name = f"{self.source_name.upper()}{key_name_suffix}"
        logger.debug(f"Buscando API key en variable de entorno: '{env_var_name}'")
        api_key = config_loader.get_secret(env_var_name)
        if not api_key:
            logger.warning(f"No se encontró la API key en la variable de entorno '{env_var_name}'. "
                           f"La API '{self.source_name}' podría no funcionar.")
        else:
             # ¡Importante! No logueamos la clave en sí por seguridad.
             logger.info(f"API key '{env_var_name}' encontrada para la fuente '{self.source_name}'.")
        return api_key

    def get_standard_job_dict(self) -> Dict[str, Any]:
        """
        Devuelve un diccionario vacío con las claves estándar esperadas para una oferta.

        Puede ser útil en las clases hijas para empezar a construir el resultado
        asegurando que todas las claves estándar estén presentes (aunque sea con valor None).

        Returns:
            Dict[str, Any]: Un diccionario con claves estándar inicializadas a None.
        """
        return {
            'titulo': None,
            'empresa': None,
            'ubicacion': None,
            'descripcion': None,
            'fecha_publicacion': None,
            'url': None,
            'fuente': self.source_name # Podemos pre-rellenar la fuente aquí.
            # Añadir más claves estándar si es necesario
        }

    # Podríamos añadir más helpers si vemos patrones comunes al implementar
    # los diferentes clientes API (ej: para paginación, parseo de fechas, etc.).

# --- Fin de la Clase Base ---

# Ejemplo de cómo una clase hija la usaría (¡esto NO va en este archivo!):
# class AdzunaClient(BaseAPIClient):
#     def __init__(self, http_client: HTTPClient, config: dict):
#         # Llamamos al init de la clase base pasándole nuestro nombre y el cliente http.
#         super().__init__(source_name="adzuna", http_client=http_client, config=config)
#         # Podemos añadir inicialización específica de Adzuna aquí si hace falta.
#         self.adzuna_app_id = self._get_api_key("_APP_ID") # Usamos el helper!
#         self.adzuna_app_key = self._get_api_key("_APP_KEY") # Usamos el helper!

#     def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
#         logger.info(f"[{self.source_name}] Buscando trabajos con parámetros: {search_params}")
#         if not self.adzuna_app_id or not self.adzuna_app_key:
#              logger.error(f"[{self.source_name}] Faltan credenciales API (APP_ID o APP_KEY). No se puede buscar.")
#              return [] # Devolvemos lista vacía si faltan claves.

#         # ... aquí iría la lógica para construir la URL de Adzuna ...
#         api_url = "https://api.adzuna.com/v1/api/jobs/gb/search/1" # Ejemplo URL base
#         params = {
#              'app_id': self.adzuna_app_id,
#              'app_key': self.adzuna_app_key,
#              'results_per_page': self.config.get('results_per_page', 50),
#              'what': ' '.join(search_params.get('keywords', [])),
#              'where': search_params.get('location', 'gb'), # Ejemplo
#              # ... otros parámetros de Adzuna ...
#         }

#         response = self.http_client.get(api_url, params=params) # Usamos el http_client heredado!

#         if not response or response.status_code != 200:
#             logger.error(f"[{self.source_name}] Error al obtener trabajos de la API. Status: {response.status_code if response else 'N/A'}")
#             return []

#         api_data = response.json() # Obtenemos el JSON de la respuesta.
#         ofertas_normalizadas = []
#         for job_data in api_data.get('results', []):
#              # ... aquí iría la lógica para mapear los campos de Adzuna a nuestro formato estándar ...
#              oferta = self.get_standard_job_dict() # Empezamos con el dict estándar.
#              oferta['titulo'] = job_data.get('title')
#              oferta['empresa'] = job_data.get('company', {}).get('display_name')
#              # ... mapear los demás campos ...
#              oferta['url'] = job_data.get('redirect_url')
#              ofertas_normalizadas.append(oferta)

#         logger.info(f"[{self.source_name}] Se encontraron {len(ofertas_normalizadas)} ofertas.")
#         return ofertas_normalizadas