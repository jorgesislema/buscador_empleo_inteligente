# -*- coding: utf-8 -*-
# /src/apis/arbeitnow_client.py

"""
Cliente API específico para Arbeitnow (arbeitnow.com).

Hereda de BaseAPIClient y se comunica con la API JSON pública y gratuita
para obtener ofertas de empleo remoto. ¡Otra API sencilla!
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from src.apis.base_api import BaseAPIClient
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_FETCH_ARBEITNOW = 10

class ArbeitnowClient(BaseAPIClient):
    API_ENDPOINT = "https://arbeitnow.com/api/job-board-api"

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="arbeitnow", http_client=http_client, config=config)
        logger.info(f"[{self.source_name}] Cliente API inicializado. Endpoint: {self.API_ENDPOINT}")

    def _parse_arbeitnow_date(self, timestamp_ms: Optional[int]) -> Optional[str]:
        if timestamp_ms is None:
            return None
        try:
            dt_object = datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=datetime.timezone.utc)
            return dt_object.strftime('%Y-%m-%d')
        except (ValueError, TypeError) as e:
            logger.warning(f"[{self.source_name}] No se pudo parsear el timestamp: '{timestamp_ms}', error: {e}")
            return None

    def _normalize_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not job_data or not isinstance(job_data, dict):
            return None

        oferta = self.get_standard_job_dict()
        oferta['titulo'] = job_data.get('title')
        oferta['empresa'] = job_data.get('company_name')
        oferta['ubicacion'] = job_data.get('location') or 'Remote'
        oferta['fecha_publicacion'] = self._parse_arbeitnow_date(job_data.get('created_at'))
        oferta['url'] = job_data.get('url')
        oferta['descripcion'] = job_data.get('description')

        extra_info = []
        tags = job_data.get('tags')
        if tags and isinstance(tags, list):
            extra_info.append(f"Tags: {', '.join(tags)}")
        job_types = job_data.get('job_types')
        if job_types and isinstance(job_types, list):
            extra_info.append(f"Tipo: {', '.join(job_types)}")
        if job_data.get('remote') and 'Remote' not in oferta['ubicacion']:
            extra_info.append("Modalidad: Remote")

        if extra_info:
            oferta['descripcion'] = (oferta['descripcion'] or "") + "\n\n[" + " | ".join(extra_info) + "]"

        if oferta['titulo'] and oferta['url']:
            return oferta
        else:
            logger.warning(f"[{self.source_name}] Oferta omitida por faltar título o URL. Slug: {job_data.get('slug', 'N/A')}")
            return None

    def fetch_jobs(self, search_params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Obteniendo trabajos desde API Arbeitnow: {self.API_ENDPOINT}")
        all_job_offers = []
        current_page = 1

        # Podemos usar search_params en un futuro para filtrar resultados
        # Por ahora, lo registramos pero no lo usamos en la API
        if search_params:
            logger.debug(f"[{self.source_name}] Parámetros de búsqueda recibidos: {search_params}")

        while current_page <= MAX_PAGES_TO_FETCH_ARBEITNOW:
            logger.info(f"[{self.source_name}] Procesando página {current_page}...")
            params = {'page': current_page}
            response = self.http_client.get(self.API_ENDPOINT, params=params)

            if not response or response.status_code != 200:
                logger.error(f"[{self.source_name}] Error API ({response.status_code if response else 'N/A'}) en página {current_page}.")
                if response:
                    logger.error(f"Respuesta: {response.text[:200]}")
                break

            try:
                api_data = response.json()
                jobs_list_from_api = api_data.get('data')

                if isinstance(jobs_list_from_api, list) and jobs_list_from_api:
                    logger.info(f"[{self.source_name}] Recibidas {len(jobs_list_from_api)} ofertas (pág. {current_page}).")
                    for job_data in jobs_list_from_api:
                        oferta_normalizada = self._normalize_job(job_data)
                        if oferta_normalizada:
                            all_job_offers.append(oferta_normalizada)
                else:
                    logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}. Fin.")
                    break
            except json.JSONDecodeError as e:
                logger.error(f"[{self.source_name}] Error decodificando JSON: {e}")
                break
            except Exception as e:
                logger.exception(f"[{self.source_name}] Error inesperado procesando respuesta: {e}")
                break

            current_page += 1

        logger.info(f"[{self.source_name}] Finalizada la búsqueda. {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers


if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()
    client = ArbeitnowClient(http_client=http_client)

    print("\n--- Iniciando prueba de ArbeitnowClient ---")
    ofertas = client.fetch_jobs()
    print(f"\nSe obtuvieron {len(ofertas)} ofertas.")

    if ofertas:
        pprint.pprint(ofertas[0])
    else:
        print("\nNo se obtuvieron ofertas.")

    http_client.close()
