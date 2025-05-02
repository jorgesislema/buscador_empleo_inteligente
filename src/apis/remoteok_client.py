# -*- coding: utf-8 -*-
# /src/apis/remoteok_client.py

"""
Cliente API específico para Remote OK (remoteok.com / remoteok.io).

Hereda de BaseAPIClient y se comunica con la API JSON pública de Remote OK
para obtener ofertas de empleo remoto. ¡Mucho más fácil que scrapear! Yay!
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime # Para parsear fechas de la API
import json # Para manejar posibles errores de JSON

# Nuestras herramientas base y el cliente HTTP
from src.apis.base_api import BaseAPIClient
from src.utils.http_client import HTTPClient
# No necesitamos config_loader aquí si la API no requiere clave.

# Logger para este cliente API
logger = logging.getLogger(__name__)

class RemoteOkClient(BaseAPIClient):
    """
    Implementación del cliente API para Remote OK.
    Utiliza la API JSON pública (generalmente no requiere clave).
    """
    # URL de la API. ¡Verificar si es .com o .io!
    API_ENDPOINT = "https://remoteok.com/api" # def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador del cliente API de Remote OK.

        Args:
            http_client (HTTPClient): Instancia del cliente HTTP.
            config (Optional[Dict[str, Any]]): Config específica (si la hubiera).
        """
        super().__init__(source_name="remoteok", http_client=http_client, config=config)
        logger.info(f"[{self.source_name}] Cliente API inicializado. Endpoint: {self.API_ENDPOINT}")
        logger.info(f"[{self.source_name}] Usando API JSON pública. ¡No requiere API Key!")


    def _parse_api_date(self, date_str_iso: Optional[str]) -> Optional[str]:
        """
        Parsea la fecha que viene de la API (formato ISO 8601) a 'YYYY-MM-DD'.

        Args:
            date_str_iso (Optional[str]): Fecha en formato ISO (ej: "2024-05-01T10:00:00Z").

        Returns:
            Optional[str]: Fecha en formato 'YYYY-MM-DD' o None si falla.
        """
        if not date_str_iso:
            return None
        try:
            # datetime.fromisoformat maneja el formato ISO estándar, incluyendo la 'Z' (UTC).
            dt_object = datetime.fromisoformat(date_str_iso.replace('Z', '+00:00')) # Aseguramos compatibilidad zona horaria
            return dt_object.strftime('%Y-%m-%d')
        except ValueError:
            logger.warning(f"[{self.source_name}] No se pudo parsear la fecha ISO: '{date_str_iso}'")
            return None # O devolver la cadena original? Mejor None para consistencia.
        except Exception as e:
             logger.error(f"[{self.source_name}] Error inesperado parseando fecha '{date_str_iso}': {e}")
             return None


    def _normalize_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convierte un diccionario de oferta de la API de Remote OK
        a nuestro formato estándar interno.

        Args:
            job_data (Dict[str, Any]): Diccionario con datos de una oferta desde la API.

        Returns:
            Optional[Dict[str, Any]]: Diccionario normalizado o None si faltan datos clave.
        """
        if not job_data or not isinstance(job_data, dict):
            return None

        # Empezamos con nuestro diccionario estándar vacío.
        oferta = self.get_standard_job_dict()

        # Mapeamos los campos de la API a nuestras claves estándar.
        # ¡Estos nombres de campo de la API son suposiciones! Hay que verificar la respuesta real.
        oferta['titulo'] = job_data.get('position') # oferta['empresa'] = job_data.get('company')  # # La ubicación en Remote OK puede ser genérica o no existir.
        oferta['ubicacion'] = job_data.get('location') if job_data.get('location') else "Remote" # oferta['fecha_publicacion'] = self._parse_api_date(job_data.get('date')) # # La URL suele ser el enlace directo para aplicar o ver más.
        oferta['url'] = job_data.get('url') # # La descripción suele venir en HTML. La guardamos tal cual por ahora.
        oferta['descripcion'] = job_data.get('description') # # Añadir tags/skills a la descripción si existen.
        tags = job_data.get('tags', []) # if tags and isinstance(tags, list):
            skills_str = f"\n\nSkills/Tags: {', '.join(tags)}"
            oferta['descripcion'] = (oferta['descripcion'] or "") + skills_str

        # Verificamos si tenemos lo mínimo indispensable (título y URL).
        if oferta['titulo'] and oferta['url']:
            return oferta
        else:
            logger.warning(f"[{self.source_name}] Oferta API omitida por faltar título o URL. Data: {job_data.get('id', 'N/A')}")
            return None


    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Implementación de la obtención de trabajos desde la API de Remote OK.

        NOTA: La API pública básica de Remote OK podría no soportar filtros
        por keywords o location directamente. Este método descargará las últimas
        ofertas y el filtrado se hará posteriormente.
        """
        logger.info(f"[{self.source_name}] Obteniendo trabajos desde la API: {self.API_ENDPOINT}")
        # Ignoramos los search_params por ahora, asumiendo que la API básica no los usa.
        if search_params.get('keywords') or search_params.get('location'):
             logger.info(f"[{self.source_name}] Nota: Los parámetros de búsqueda ({search_params}) probablemente"
                         f" sean ignorados por la API pública básica de RemoteOK. Se descargarán las últimas ofertas.")

        all_job_offers = []

        # Hacemos la petición GET a la API usando nuestro http_client.
        response = self.http_client.get(self.API_ENDPOINT)

        if not response:
            logger.error(f"[{self.source_name}] No se recibió respuesta de la API.")
            return all_job_offers # Devolver lista vacía.

        if response.status_code != 200:
            logger.error(f"[{self.source_name}] Error de la API. Status Code: {response.status_code}. Respuesta: {response.text[:200]}")
            return all_job_offers # Devolver lista vacía.

        # ¡Éxito! Intentamos parsear el JSON.
        try:
            raw_data = response.json()

            # --- Procesamiento de la Respuesta JSON ---
            # Algunas APIs JSON devuelven una lista donde el primer elemento [0]
            # contiene metadatos o información legal, y los trabajos empiezan desde [1].
            # ¡Hay que verificar la estructura real de la API de Remote OK!
            # EJEMPLO de cómo saltar el primer elemento si fuera necesario:
            if isinstance(raw_data, list) and len(raw_data) > 1 and isinstance(raw_data[0], dict) and 'legal' in raw_data[0]:
                 logger.debug(f"[{self.source_name}] Detectado posible metadato en el índice [0]. Saltando primer elemento.")
                 jobs_list_from_api = raw_data[1:] # elif isinstance(raw_data, list):
                 # Si es una lista pero no detectamos metadata, asumimos que toda la lista son trabajos.
                 jobs_list_from_api = raw_data
            else:
                 logger.error(f"[{self.source_name}] La respuesta de la API no es una lista como se esperaba. Tipo recibido: {type(raw_data)}")
                 return all_job_offers

            logger.info(f"[{self.source_name}] Recibidas {len(jobs_list_from_api)} ofertas crudas de la API.")

            # Normalizamos cada oferta al formato estándar.
            for job_data in jobs_list_from_api:
                oferta_normalizada = self._normalize_job(job_data)
                if oferta_normalizada:
                    all_job_offers.append(oferta_normalizada)

        except json.JSONDecodeError as e:
            logger.error(f"[{self.source_name}] Error al decodificar JSON de la API: {e}. Respuesta recibida (inicio): {response.text[:200]}")
        except Exception as e:
            logger.exception(f"[{self.source_name}] Error inesperado al procesar respuesta de la API: {e}")

        logger.info(f"[{self.source_name}] Búsqueda API finalizada. {len(all_job_offers)} ofertas normalizadas.")
        return all_job_offers


# --- Ejemplo de uso ---
if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    # ¡Importante! No necesitamos una config específica de settings.yaml aquí,
    # pero sí necesitamos el HTTPClient.
    http_client = HTTPClient()

    # Creamos el cliente API. No necesita config especial por ahora.
    client = RemoteOkClient(http_client=http_client)

    # Los search_params probablemente se ignoren, pero los pasamos por consistencia.
    search_params = {
        'keywords': ['python', 'backend'],
        'location': 'Remote'
    }

    print(f"\n--- Iniciando prueba de RemoteOkClient ---")
    print(f"Llamando a la API: {client.API_ENDPOINT}")
    print(f"(Parámetros de búsqueda {search_params} probablemente ignorados por la API)")

    try:
        ofertas = client.fetch_jobs(search_params)
        print(f"\n--- Prueba finalizada ---")
        print(f"Se obtuvieron {len(ofertas)} ofertas de la API.")

        if ofertas:
            print("\nEjemplo de la primera oferta obtenida:")
            pprint.pprint(ofertas[0])
        else:
            print("\nNo se obtuvieron ofertas o hubo un error.")

    except Exception as e:
        logger.exception("Ocurrió un error durante la prueba del cliente API Remote OK.")
        print(f"\n--- Ocurrió un error durante la prueba: {e} ---")

    finally:
        http_client.close()