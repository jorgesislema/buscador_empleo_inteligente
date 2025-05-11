# -*- coding: utf-8 -*-
# /src/apis/remoteok_client.py

"""
Cliente API para Remote OK.
Consume la API JSON pública y normaliza las ofertas de trabajo remoto para el esquema interno.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from src.apis.base_api import BaseAPIClient
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)

class RemoteOkClient(BaseAPIClient):
    API_ENDPOINT = "https://remoteok.com/api"

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="remoteok", http_client=http_client, config=config)
        logger.info(f"[{self.source_name}] Cliente API inicializado. Endpoint: {self.API_ENDPOINT}")

    def _parse_api_date(self, date_str_iso: Optional[str]) -> Optional[str]:
        if not date_str_iso:
            return None
        try:
            dt_object = datetime.fromisoformat(date_str_iso.replace('Z', '+00:00'))
            return dt_object.strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"[{self.source_name}] Error al parsear fecha ISO: {date_str_iso} - {e}")
            return None

    def _normalize_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not job_data or not isinstance(job_data, dict):
            return None

        oferta = self.get_standard_job_dict()
        oferta['titulo'] = job_data.get('position')
        oferta['empresa'] = job_data.get('company')
        oferta['ubicacion'] = job_data.get('location') or "Remote"
        oferta['fecha_publicacion'] = self._parse_api_date(job_data.get('date'))
        oferta['url'] = job_data.get('url')
        oferta['descripcion'] = job_data.get('description') or ""

        tags = job_data.get('tags')
        if tags and isinstance(tags, list):
            oferta['descripcion'] += f"\n\nSkills/Tags: {', '.join(tags)}"

        if oferta['titulo'] and oferta['url']:
            return oferta
        logger.warning(f"[{self.source_name}] Oferta omitida: falta título o URL. ID: {job_data.get('id', 'N/A')}")
        return None

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Consultando API pública de Remote OK")
        all_job_offers = []

        response = self.http_client.get(self.API_ENDPOINT)
        if not response or response.status_code != 200:
            logger.error(f"[{self.source_name}] Error en la API. Status: {response.status_code if response else 'N/A'}")
            return []

        try:
            if not response:
                logger.error(f"[{self.source_name}] Respuesta nula de la API.")
                return []
            raw_data = response.json()
            if isinstance(raw_data, list) and len(raw_data) > 1 and isinstance(raw_data[0], dict) and 'legal' in raw_data[0]:
                jobs_list = raw_data[1:]
            elif isinstance(raw_data, list):
                jobs_list = raw_data
            else:
                logger.error(f"[{self.source_name}] Estructura inesperada en JSON de respuesta.")
                return []

            for job in jobs_list:
                normalizado = self._normalize_job(job)
                if normalizado:
                    all_job_offers.append(normalizado)

        except json.JSONDecodeError as e:
            logger.error(f"[{self.source_name}] Error al decodificar JSON: {e}")
        except Exception as e:
            logger.exception(f"[{self.source_name}] Excepción inesperada procesando resultados: {e}")

        logger.info(f"[{self.source_name}] {len(all_job_offers)} ofertas normalizadas.")
        return all_job_offers


if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()
    client = RemoteOkClient(http_client=http_client)

    search_params = {
        'keywords': ['python', 'backend'],
        'location': 'Remote'
    }

    print("\n--- Iniciando prueba de RemoteOkClient ---")
    ofertas = client.fetch_jobs(search_params)
    print(f"\nSe obtuvieron {len(ofertas)} ofertas.")

    if ofertas:
        pprint.pprint(ofertas[0])

    http_client.close()
