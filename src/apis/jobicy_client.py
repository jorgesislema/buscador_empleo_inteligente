# -*- coding: utf-8 -*-
# /src/apis/jobicy_client.py

"""
Cliente API para Jobicy (jobicy.com).
Consulta su API pública (sin autenticación) y normaliza los datos a nuestro esquema estándar.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from urllib.parse import quote_plus

from src.apis.base_api import BaseAPIClient
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)

class JobicyClient(BaseAPIClient):
    DEFAULT_API_ENDPOINT = "https://jobicy.com/api/v2/remote-jobs"

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="jobicy", http_client=http_client, config=config)
        self.api_url_base = self.config.get('api_url', self.DEFAULT_API_ENDPOINT)
        logger.info(f"[{self.source_name}] Cliente API inicializado. Endpoint base: {self.api_url_base}")

    def _parse_jobicy_date(self, date_unix_ts: Optional[int]) -> Optional[str]:
        if date_unix_ts is None:
            return None
        try:
            dt_object = datetime.utcfromtimestamp(int(date_unix_ts))
            return dt_object.strftime('%Y-%m-%d')
        except (ValueError, TypeError) as e:
            logger.warning(f"[{self.source_name}] No se pudo parsear el timestamp Unix: {date_unix_ts}, error: {e}")
            return None

    def _build_api_url(self, keywords: List[str]) -> str:
        url = self.api_url_base
        if keywords:
            tag = quote_plus(keywords[0].strip().lower())
            separator = '&' if '?' in url else '?'
            url += f"{separator}tag={tag}"
        return url

    def _normalize_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not job_data or not isinstance(job_data, dict):
            return None

        oferta = self.get_standard_job_dict()
        oferta['titulo'] = job_data.get('jobTitle')
        oferta['empresa'] = job_data.get('companyName')
        oferta['ubicacion'] = job_data.get('jobGeo', 'Remote')
        oferta['fecha_publicacion'] = self._parse_jobicy_date(job_data.get('pubDate'))
        oferta['url'] = job_data.get('url')
        oferta['descripcion'] = job_data.get('jobExcerpt')

        extra_info = []
        job_type = job_data.get('jobType')
        if job_type and isinstance(job_type, list):
            extra_info.append(f"Tipo: {', '.join(job_type)}")
        job_level = job_data.get('jobLevel')
        if job_level:
            extra_info.append(f"Nivel: {job_level}")
        job_industry = job_data.get('jobIndustry')
        if job_industry and isinstance(job_industry, list):
            extra_info.append(f"Industria: {', '.join(job_industry)}")

        if extra_info:
            oferta['descripcion'] = (oferta['descripcion'] or "") + "\n\n" + " | ".join(extra_info)

        if oferta['titulo'] and oferta['url']:
            return oferta
        else:
            logger.warning(f"[{self.source_name}] Oferta omitida por faltar título o URL. ID: {job_data.get('id', 'N/A')}")
            return None

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Obteniendo trabajos desde la API Jobicy...")
        all_job_offers = []
        keywords = search_params.get('keywords', [])
        api_url_final = self._build_api_url(keywords)

        response = self.http_client.get(api_url_final)
        if not response or response.status_code != 200:
            logger.error(f"[{self.source_name}] Error al obtener datos. Status: {response.status_code if response else 'N/A'}")
            return all_job_offers

        try:
            api_data = response.json()
            jobs_list_from_api = api_data.get('jobs')
            if isinstance(jobs_list_from_api, list):
                for job_data in jobs_list_from_api:
                    oferta = self._normalize_job(job_data)
                    if oferta:
                        all_job_offers.append(oferta)
            else:
                logger.error(f"[{self.source_name}] Estructura de respuesta inesperada: no contiene lista en 'jobs'.")
        except Exception as e:
            logger.exception(f"[{self.source_name}] Error procesando respuesta JSON: {e}")

        logger.info(f"[{self.source_name}] Búsqueda API finalizada. {len(all_job_offers)} ofertas normalizadas.")
        return all_job_offers


if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()
    client = JobicyClient(http_client=http_client)

    search_params = {
        'keywords': ['python', 'data'],
        'location': 'Remote'
    }

    print("\n--- Iniciando prueba de JobicyClient ---")
    ofertas = client.fetch_jobs(search_params)
    print(f"\nSe obtuvieron {len(ofertas)} ofertas.")

    if ofertas:
        pprint.pprint(ofertas[0])

    http_client.close()
