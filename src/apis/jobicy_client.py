# -*- coding: utf-8 -*-
# /src/apis/jobicy_client.py

"""
Cliente API específico para Jobicy (jobicy.com).

Hereda de BaseAPIClient y se comunica con la API JSON pública de Jobicy
para obtener ofertas de empleo remoto. ¡Otra API para la colección!
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime # Para parsear fechas de la API
import json # Para manejar posibles errores de JSON
from urllib.parse import quote_plus # Para parámetros URL

# Nuestras herramientas base y utilidades
from src.apis.base_api import BaseAPIClient
from src.utils.http_client import HTTPClient
# Podríamos necesitar config_loader si hacemos la URL configurable.
from src.utils import config_loader

# Logger para este cliente API
logger = logging.getLogger(__name__)

class JobicyClient(BaseAPIClient):
    """
    Implementación del cliente para la API pública de Jobicy.
    Generalmente no requiere API Key.
    """
    # URL por defecto de la API V2 de Jobicy. Podría cambiar o hacerse configurable.
    DEFAULT_API_ENDPOINT = "https://jobicy.com/api/v2/remote-jobs" # def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador del cliente API de Jobicy.

        Args:
            http_client (HTTPClient): Instancia del cliente HTTP.
            config (Optional[Dict[str, Any]]): Config específica (podría tener 'api_url').
        """
        super().__init__(source_name="jobicy", http_client=http_client, config=config)

        # Buscamos una URL específica en la config, si no, usamos la default.
        self.api_url_base = self.config.get('api_url', self.DEFAULT_API_ENDPOINT)
        logger.info(f"[{self.source_name}] Cliente API inicializado. Endpoint base: {self.api_url_base}")
        # No necesitamos API Key aquí, ¡qué alivio!


    def _parse_jobicy_date(self, date_unix_ts: Optional[int]) -> Optional[str]:
        """
        Parsea la fecha que viene de la API de Jobicy (parece ser timestamp Unix) a 'YYYY-MM-DD'.

        Args:
            date_unix_ts (Optional[int]): Timestamp Unix (segundos desde 1970-01-01 UTC).

        Returns:
            Optional[str]: Fecha en formato 'YYYY-MM-DD' o None si falla.
        """
        if date_unix_ts is None: # Acepta None, no solo int.
            return None
        try:
            # Convertir timestamp Unix a datetime object (UTC).
            dt_object = datetime.utcfromtimestamp(int(date_unix_ts))
            return dt_object.strftime('%Y-%m-%d')
        except (ValueError, TypeError) as e:
            logger.warning(f"[{self.source_name}] No se pudo parsear el timestamp Unix: '{date_unix_ts}', error: {e}")
            return None # O devolver el timestamp original como string? Mejor None.
        except Exception as e:
             logger.error(f"[{self.source_name}] Error inesperado parseando timestamp '{date_unix_ts}': {e}")
             return None

    def _build_api_url(self, keywords: List[str]) -> str:
        """
        Construye la URL final de la API, potencialmente añadiendo filtros.

        Jobicy API V2 permite filtros como ?tag=, ?count=, ?geo=.
        Intentaremos usar la primera keyword como tag. ¡VERIFICAR!

        Args:
            keywords (List[str]): Palabras clave de búsqueda.

        Returns:
            str: La URL completa de la API a consultar.
        """
        url = self.api_url_base
        params = {}
        # Intentamos usar la primera keyword como tag de filtro.
        if keywords:
            tag_query = quote_plus(keywords[0].strip().lower())
            params['tag'] = tag_query # logger.info(f"[{self.source_name}] Aplicando filtro por tag (primera keyword): '{tag_query}'")
        else:
             logger.info(f"[{self.source_name}] No se especificaron keywords, obteniendo últimas ofertas generales.")

        # Podríamos añadir otros parámetros si quisiéramos limitar el número (?count=) o geografía (?geo=).
        # params['count'] = 50 # Ejemplo

        if params:
             query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
             # Asegurarnos de añadir el separador correcto (? o &)
             separator = '&' if '?' in url else '?'
             url += separator + query_string

        logger.debug(f"[{self.source_name}] URL API final construida: {url}")
        return url


    def _normalize_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convierte un diccionario de oferta de la API de Jobicy
        a nuestro formato estándar interno.

        Args:
            job_data (Dict[str, Any]): Diccionario con datos de una oferta desde la API Jobicy.

        Returns:
            Optional[Dict[str, Any]]: Diccionario normalizado o None si faltan datos clave.
        """
        if not job_data or not isinstance(job_data, dict):
            return None

        oferta = self.get_standard_job_dict()

        # Mapeamos los campos de la API Jobicy a nuestras claves estándar.
        # ¡Nombres de campo basados en ejemplos de API V2! ¡VERIFICAR RESPUESTA REAL!
        oferta['titulo'] = job_data.get('jobTitle')      # oferta['empresa'] = job_data.get('companyName')   # # Jobicy tiene 'jobGeo' para restricciones geográficas. Lo ponemos en ubicación.
        oferta['ubicacion'] = job_data.get('jobGeo', 'Remote') # if not oferta['ubicacion']: oferta['ubicacion'] = 'Remote' # Asegurar que al menos diga Remote
        # Usamos nuestro parser para la fecha (puede estar en 'pubDate'). Espera un timestamp Unix.
        oferta['fecha_publicacion'] = self._parse_jobicy_date(job_data.get('pubDate')) # # La URL es el enlace a la oferta (probablemente en Jobicy o externa).
        oferta['url'] = job_data.get('url')          # # Usamos 'jobExcerpt' como descripción (suele ser corta).
        oferta['descripcion'] = job_data.get('jobExcerpt') # # Podemos añadir otros datos útiles a la descripción:
        extra_info = []
        job_type = job_data.get('jobType') # Suele ser una lista: ['Full-time'] if job_type and isinstance(job_type, list):
            extra_info.append(f"Tipo: {', '.join(job_type)}")
        job_level = job_data.get('jobLevel') # Ej: "Senior" if job_level:
            extra_info.append(f"Nivel: {job_level}")
        job_industry = job_data.get('jobIndustry') # Suele ser lista: ['IT'] if job_industry and isinstance(job_industry, list):
             extra_info.append(f"Industria: {', '.join(job_industry)}")

        if extra_info:
             oferta['descripcion'] = (oferta['descripcion'] or "") + "\n\n" + " | ".join(extra_info)

        # Verificamos si tenemos lo mínimo (título y URL).
        if oferta['titulo'] and oferta['url']:
            return oferta
        else:
            logger.warning(f"[{self.source_name}] Oferta API Jobicy omitida por faltar título o URL. ID: {job_data.get('id', 'N/A')}")
            return None


    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Implementación de la obtención de trabajos desde la API de Jobicy.
        Intenta usar la primera keyword como filtro 'tag'.
        """
        logger.info(f"[{self.source_name}] Obteniendo trabajos desde la API Jobicy...")
        all_job_offers = []

        # Construimos la URL final, posiblemente con filtro tag.
        keywords = search_params.get('keywords', [])
        api_url_final = self._build_api_url(keywords)

        # Hacemos la petición GET.
        response = self.http_client.get(api_url_final)

        if not response or response.status_code != 200:
            logger.error(f"[{self.source_name}] Error al obtener datos de la API Jobicy. Status: {response.status_code if response else 'N/A'}. URL: {api_url_final}")
            if response: logger.error(f"Respuesta API (inicio): {response.text[:200]}")
            return all_job_offers

        # Parseamos el JSON.
        try:
            api_data = response.json()

            # --- Procesar Respuesta JSON ---
            # Buscamos la lista de trabajos. ¿Está bajo la clave 'jobs'?
            jobs_list_from_api = api_data.get('jobs') # if jobs_list_from_api and isinstance(jobs_list_from_api, list):
                logger.info(f"[{self.source_name}] Recibidas {len(jobs_list_from_api)} ofertas crudas de la API Jobicy.")
                # Normalizamos cada oferta.
                for job_data in jobs_list_from_api:
                    oferta_normalizada = self._normalize_job(job_data)
                    if oferta_normalizada:
                        all_job_offers.append(oferta_normalizada)
                # ¿La API devuelve info de paginación? Probablemente no la básica.
            elif isinstance(jobs_list_from_api, list) and not jobs_list_from_api:
                 logger.info(f"[{self.source_name}] La API de Jobicy devolvió 0 ofertas para estos criterios.")
            else:
                 logger.error(f"[{self.source_name}] La respuesta JSON de Jobicy no contiene una lista de trabajos en la clave esperada ('jobs'?). Respuesta: {str(api_data)[:500]}")

        except json.JSONDecodeError as e:
            logger.error(f"[{self.source_name}] Error al decodificar JSON de la API Jobicy: {e}. Respuesta: {response.text[:200]}")
        except Exception as e:
            logger.exception(f"[{self.source_name}] Error inesperado al procesar API de Jobicy: {e}")

        logger.info(f"[{self.source_name}] Búsqueda API finalizada. {len(all_job_offers)} ofertas normalizadas.")
        return all_job_offers


# --- Ejemplo de uso ---
if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()

    # Creamos el cliente API. No necesita config especial por ahora.
    # Podríamos pasarle una config si quisiéramos definir la api_url en settings.yaml
    # jobicy_config = config_loader.get_config().get('sources',{}).get('apis',{}).get('jobicy',{})
    # client = JobicyClient(http_client=http_client, config=jobicy_config)
    client = JobicyClient(http_client=http_client)


    # Parámetros de búsqueda (intentaremos usar la primera keyword como tag)
    search_params = {
        'keywords': ['python', 'data'],
        'location': 'Remote' # Ignorado por ahora
    }

    print(f"\n--- Iniciando prueba de JobicyClient ---")
    print(f"Llamando a la API Jobicy (intentando filtrar por tag='{search_params['keywords'][0]}')")

    try:
        ofertas = client.fetch_jobs(search_params)
        print(f"\n--- Prueba finalizada ---")
        print(f"Se obtuvieron {len(ofertas)} ofertas de la API.")

        if ofertas:
            print("\nEjemplo de la primera oferta obtenida:")
            pprint.pprint(ofertas[0])
        else:
            print("\nNo se obtuvieron ofertas (¿API disponible? ¿Respuesta válida?).")

    except Exception as e:
        logger.exception("Ocurrió un error durante la prueba del cliente API Jobicy.")
        print(f"\n--- Ocurrió un error durante la prueba: {e} ---")

    finally:
        http_client.close()