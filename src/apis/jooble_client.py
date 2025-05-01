# -*- coding: utf-8 -*-
# /src/apis/jooble_client.py

"""
Cliente API específico para Jooble.

Hereda de BaseAPIClient y se comunica con la API REST de Jooble
para obtener ofertas de empleo. Usa una API Key para autenticación.
¡Mucho mejor que scrapear su web! 😉
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime # Para parsear fechas de la API
import json # Para manejar posibles errores de JSON

# Nuestras herramientas base y utilidades
from src.apis.base_api import BaseAPIClient
from src.utils.http_client import HTTPClient
from src.utils import config_loader # Para obtener la API key de forma segura

# Logger para este cliente API
logger = logging.getLogger(__name__)

class JoobleClient(BaseAPIClient):
    """
    Implementación del cliente para la API de búsqueda de empleo de Jooble.
    Requiere una API Key configurada en las variables de entorno (.env).
    """
    # La URL base de la API de Jooble. La key se añade al final.
    API_BASE_URL = "https://jooble.org/api/" # def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador del cliente API de Jooble.

        Args:
            http_client (HTTPClient): Instancia del cliente HTTP.
            config (Optional[Dict[str, Any]]): Config específica (si la hubiera).
        """
        super().__init__(source_name="jooble", http_client=http_client, config=config)

        # Obtenemos la API Key de forma segura desde .env usando nuestro helper.
        self.api_key = self._get_api_key("JOOBLE_API_KEY") # Usamos el sufijo por defecto _API_KEY

        if not self.api_key:
            logger.error(f"[{self.source_name}] ¡API Key no encontrada en la variable de entorno JOOBLE_API_KEY! El cliente no funcionará.")
            # Podríamos lanzar un error aquí para que la aplicación se detenga si la key es vital.
            # raise ValueError("JOOBLE_API_KEY no configurada en .env")
            self.api_endpoint = None # Dejamos el endpoint como None si no hay key
        else:
            # Construimos la URL completa del endpoint añadiendo la key.
            self.api_endpoint = f"{self.API_BASE_URL.rstrip('/')}/{self.api_key}"
            logger.info(f"[{self.source_name}] Cliente API inicializado. Endpoint configurado.")
            # No logueamos el endpoint completo por seguridad (contiene la key).


    def _parse_jooble_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Parsea la fecha que viene de la API de Jooble a 'YYYY-MM-DD'.
        El formato de Jooble puede variar ("updated": "YYYY-MM-DD HH:MM:SS"). ¡Verificar!

        Args:
            date_str (Optional[str]): Fecha en formato string desde la API.

        Returns:
            Optional[str]: Fecha en formato 'YYYY-MM-DD' o None si falla.
        """
        if not date_str:
            return None
        try:
            # Intentamos parsear asumiendo formato 'YYYY-MM-DD HH:MM:SS' u otros comunes.
            # Jooble a veces solo da la fecha, a veces fecha y hora.
            # dateutil.parser es más flexible pero añade dependencia. Usemos datetime.
            # Intentar formato con hora:
            try:
                 dt_object = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                 return dt_object.strftime('%Y-%m-%d')
            except ValueError:
                 # Si falla, intentar solo con fecha:
                 try:
                      dt_object = datetime.strptime(date_str, '%Y-%m-%d')
                      return dt_object.strftime('%Y-%m-%d')
                 except ValueError:
                       # Si no es ninguno, probamos con ISO por si acaso
                       try:
                            dt_object = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            return dt_object.strftime('%Y-%m-%d')
                       except ValueError:
                            logger.warning(f"[{self.source_name}] Formato de fecha Jooble no reconocido: '{date_str}'")
                            return None # O devolver la cadena original? Mejor None.
        except Exception as e:
             logger.error(f"[{self.source_name}] Error inesperado parseando fecha Jooble '{date_str}': {e}")
             return None

    def _normalize_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convierte un diccionario de oferta de la API de Jooble
        a nuestro formato estándar interno.

        Args:
            job_data (Dict[str, Any]): Diccionario con datos de una oferta desde la API Jooble.

        Returns:
            Optional[Dict[str, Any]]: Diccionario normalizado o None si faltan datos clave.
        """
        if not job_data or not isinstance(job_data, dict):
            return None

        oferta = self.get_standard_job_dict() # Empezamos con nuestro estándar.

        # Mapeamos los campos de la API Jooble a nuestras claves.
        # ¡Estos nombres de campo son suposiciones basadas en documentación pasada! ¡VERIFICAR RESPUESTA REAL!
        oferta['titulo'] = job_data.get('title')      # oferta['empresa'] = job_data.get('company')   # oferta['ubicacion'] = job_data.get('location')# # La descripción suele ser un snippet en Jooble.
        oferta['descripcion'] = job_data.get('snippet') # # Usamos nuestro parser para la fecha (puede estar en 'updated' o 'date').
        oferta['fecha_publicacion'] = self._parse_jooble_date(job_data.get('updated') or job_data.get('date')) # # El 'link' suele ser la URL a la fuente original. ¡Importante!
        oferta['url'] = job_data.get('link')          # # El salario puede venir o no.
        oferta['salario'] = job_data.get('salary')    # # El tipo de empleo (full-time, etc.) podría estar en 'type'.
        job_type = job_data.get('type') # if job_type and oferta['descripcion']:
             oferta['descripcion'] += f"\nTipo: {job_type}"
        elif job_type:
             oferta['descripcion'] = f"Tipo: {job_type}"

        # Añadimos un ID externo si la API lo proporciona (útil para seguimiento).
        # oferta['id_externo'] = job_data.get('jobId') # # Verificamos si tenemos lo mínimo (título y URL).
        if oferta['titulo'] and oferta['url']:
            return oferta
        else:
            logger.warning(f"[{self.source_name}] Oferta API Jooble omitida por faltar título o URL. ID: {job_data.get('jobId', 'N/A')}")
            return None


    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Implementación de la obtención de trabajos desde la API de Jooble.

        Realiza una petición POST con los parámetros de búsqueda en formato JSON.
        """
        if not self.api_endpoint:
            logger.error(f"[{self.source_name}] No hay API endpoint configurado (falta API key?). No se puede buscar.")
            return [] # Devolver lista vacía si no hay endpoint (por falta de key).

        logger.info(f"[{self.source_name}] Buscando trabajos vía API POST con: {search_params}")
        all_job_offers = []

        # --- Construir el cuerpo de la petición POST ---
        # Mapeamos nuestros search_params a lo que espera la API de Jooble.
        # ¡Esto necesita ser verificado con la documentación de Jooble API!
        payload = {}
        if 'keywords' in search_params and search_params['keywords']:
             # Jooble espera un string de keywords, no una lista.
            payload['keywords'] = ' '.join(search_params['keywords']) # if 'location' in search_params and search_params['location']:
             # ¿Parámetro 'location'? ¿O necesita país/región aparte?
             payload['location'] = search_params['location'] # # ¿Parámetro de página? ¿'page', 'pageNumber'? ¿Empieza en 1?
        payload['page'] = search_params.get('page', 1) # # ¿Otros parámetros útiles? searchMode, radius, etc.
        # payload['searchMode'] = 1 # Ejemplo if not payload.get('keywords') and not payload.get('location'):
             logger.error(f"[{self.source_name}] Se requiere al menos 'keywords' o 'location' para buscar en la API de Jooble.")
             return []


        logger.debug(f"[{self.source_name}] Payload para API POST: {json.dumps(payload)}")

        # --- Realizar la Petición POST ---
        # ¡Importante! Usaremos POST y enviaremos el payload como JSON.
        # Necesitamos asegurarnos de que nuestro HTTPClient (o la sesión de requests)
        # maneje bien las peticiones POST y sus posibles errores/reintentos.
        # Por ahora, usamos session.post directamente.
        try:
            response = self.http_client.session.post(
                self.api_endpoint,
                json=payload, # Enviamos los datos como JSON en el cuerpo.
                headers={'Content-Type': 'application/json'}, # Indicamos que enviamos JSON.
                timeout=self.http_client.default_timeout # Usamos el timeout del cliente.
            )
            # ¿Necesitamos llamar a raise_for_status() aquí o el manejo de errores base es suficiente?
            # Por ahora, verificaremos manualmente el status code.
            if not response: # Si http_client devolvió None (por error de conexión/timeout)
                 logger.error(f"[{self.source_name}] No se recibió respuesta de la API (http_client devolvió None).")
                 return all_job_offers

            if response.status_code != 200:
                 logger.error(f"[{self.source_name}] Error de la API Jooble. Status Code: {response.status_code}. Respuesta: {response.text[:500]}") # Loguear más texto en error
                 # ¿Podría ser un error de API key inválida (401/403)?
                 if response.status_code in [401, 403]:
                      logger.error(f"[{self.source_name}] ¡Error de autenticación/autorización! Verifica tu JOOBLE_API_KEY.")
                 return all_job_offers

            # ¡Éxito! Parseamos la respuesta JSON.
            api_data = response.json()

            # --- Procesar la Respuesta JSON ---
            # Buscamos la lista de trabajos. ¿Está bajo la clave 'jobs'?
            jobs_list_from_api = api_data.get('jobs') # if jobs_list_from_api and isinstance(jobs_list_from_api, list):
                logger.info(f"[{self.source_name}] Recibidas {len(jobs_list_from_api)} ofertas crudas de la API Jooble.")
                # Normalizamos cada oferta.
                for job_data in jobs_list_from_api:
                    oferta_normalizada = self._normalize_job(job_data)
                    if oferta_normalizada:
                        all_job_offers.append(oferta_normalizada)
                # Podríamos manejar la paginación aquí si la API devuelve info como 'totalJobs', 'totalPages'.
                # total_jobs = api_data.get('totalCount', len(jobs_list_from_api))
                # logger.info(f"Total de trabajos encontrados por la API (aprox): {total_jobs}")
            elif isinstance(jobs_list_from_api, list) and not jobs_list_from_api:
                 logger.info(f"[{self.source_name}] La API de Jooble devolvió 0 ofertas para estos criterios.")
            else:
                 logger.error(f"[{self.source_name}] La respuesta JSON de Jooble no contiene una lista de trabajos en la clave esperada ('jobs'?). Respuesta: {str(api_data)[:500]}")


        except requests.exceptions.RequestException as e:
             # Capturamos errores de la librería requests (ya logueados por http_client probablemente).
             logger.error(f"[{self.source_name}] Error de 'requests' durante la llamada API a Jooble: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"[{self.source_name}] Error al decodificar JSON de la API Jooble: {e}. Respuesta: {response.text[:200]}")
        except Exception as e:
            logger.exception(f"[{self.source_name}] Error inesperado al procesar API de Jooble: {e}")

        logger.info(f"[{self.source_name}] Búsqueda API finalizada. {len(all_job_offers)} ofertas normalizadas.")
        return all_job_offers


# --- Ejemplo de uso ---
if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    # Asegúrate de tener JOOBLE_API_KEY en tu archivo .env para que esto funcione.
    # Si no, el cliente se inicializará pero fetch_jobs devolverá lista vacía.
    http_client = HTTPClient()

    # Creamos el cliente API. No necesita config específica de settings.yaml por ahora.
    client = JoobleClient(http_client=http_client)

    # Parámetros de búsqueda
    search_params = {
        'keywords': ['python', 'data'],
        'location': 'Ecuador' # O 'Quito', o dejar vacío para buscar global? ¡Verificar API!
        # 'page': 1 # Podríamos añadir paginación si quisiéramos probarla.
    }

    print(f"\n--- Iniciando prueba de JoobleClient ---")
    print(f"Buscando trabajos vía API con: {search_params}")

    try:
        # Solo buscará si la API Key fue encontrada en __init__
        if client.api_endpoint:
             ofertas = client.fetch_jobs(search_params)
             print(f"\n--- Prueba finalizada ---")
             print(f"Se obtuvieron {len(ofertas)} ofertas de la API.")

             if ofertas:
                 print("\nEjemplo de la primera oferta obtenida:")
                 pprint.pprint(ofertas[0])
                 print("\nNOTA: La 'url' probablemente enlace a la fuente original.")
                 print("      La 'descripcion' puede ser un snippet.")
             else:
                 print("\nNo se obtuvieron ofertas (¿API Key correcta? ¿Parámetros válidos? ¿Sin resultados?).")
        else:
             print("\nPrueba omitida: API Key de Jooble no configurada en .env.")

    except Exception as e:
        logger.exception("Ocurrió un error durante la prueba del cliente API Jooble.")
        print(f"\n--- Ocurrió un error durante la prueba: {e} ---")

    finally:
        http_client.close()