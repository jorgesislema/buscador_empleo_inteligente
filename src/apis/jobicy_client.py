# -*- coding: utf-8 -*-
# /src/apis/jobicy_client.py

"""
Cliente API específico para Jobicy (jobicy.com).
(Versión con fecha corregida y filtro tag limitado/eliminado)
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

try:
    from src.apis.base_api import BaseAPIClient
    from src.utils.http_client import HTTPClient
except ImportError:
    logging.basicConfig(level=logging.WARNING)
    logging.warning("Fallo al importar módulos de src en jobicy_client...")

    class BaseAPIClient:
        def __init__(self, source_name, http_client, config):
            self.source_name = source_name
            self.http_client = http_client
            self.config = config

        def _get_api_key(self, suffix):
            return f"dummy_key_for_{suffix}"

        def get_standard_job_dict(self):
            return {}

    class HTTPClient: pass

logger = logging.getLogger(__name__)

class JobicyClient(BaseAPIClient):
    DEFAULT_API_ENDPOINT = "https://jobicy.com/api/v2/remote-jobs"

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="jobicy", http_client=http_client, config=config)
        self.api_url_base = self.config.get('api_url', self.DEFAULT_API_ENDPOINT)
        logger.info(f"[{self.source_name}] Cliente API inicializado. Endpoint base: {self.api_url_base}")

    def _parse_jobicy_date(self, date_str: Optional[str]) -> Optional[str]:
        if not date_str or not isinstance(date_str, str):
            return None
        try:
            return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
        except Exception as e:
            logger.error(f"[{self.source_name}] Error parseando fecha '{date_str}': {e}")
            return None

    def _build_api_url(self, keywords: List[str]) -> str:
        url = self.api_url_base
        logger.info(f"[{self.source_name}] Obteniendo últimas ofertas generales (sin filtro 'tag').")
        logger.debug(f"[{self.source_name}] URL API final construida: {url}")
        return url

    def _normalize_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not job_data or not isinstance(job_data, dict):
            return None

        oferta = self.get_standard_job_dict()
        oferta['titulo'] = job_data.get('jobTitle')
        oferta['empresa'] = job_data.get('companyName')
        ubic = job_data.get('jobGeo', 'Remote')
        oferta['ubicacion'] = ubic or 'Remote'
        oferta['fecha_publicacion'] = self._parse_jobicy_date(job_data.get('pubDate'))
        oferta['url'] = job_data.get('url')
        oferta['descripcion'] = job_data.get('jobExcerpt')

        extra_info: List[str] = []
        jt = job_data.get('jobType')
        if jt and isinstance(jt, list):
            extra_info.append(f"Tipo: {', '.join(jt)}")
        jl = job_data.get('jobLevel')
        if jl:
            extra_info.append(f"Nivel: {jl}")
        ji = job_data.get('jobIndustry')
        if ji and isinstance(ji, list):
            extra_info.append(f"Industria: {', '.join(ji)}")
        if extra_info:
            oferta['descripcion'] = (oferta['descripcion'] or "") + "\n\n[" + " | ".join(extra_info) + "]"

        if oferta['titulo'] and oferta['url']:
            return oferta

        logger.warning(f"[{self.source_name}] Oferta omitida (sin título/URL). ID: {job_data.get('id', 'N/A')}")
        return None

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Obteniendo trabajos desde la API Jobicy...")
        all_job_offers: List[Dict[str, Any]] = []
        keywords = search_params.get('keywords', [])
        api_url = self._build_api_url(keywords)

        response = self.http_client.get(api_url)
        if not response or response.status_code != 200:
            logger.error(f"[{self.source_name}] Error API Jobicy. Status: {response.status_code if response else 'N/A'}. URL: {api_url}")
            if response:
                logger.error(f"Respuesta (inicio): {response.text[:200]}")
            return all_job_offers

        try:
            api_data = response.json()
            jobs_list = api_data.get('jobs')
            if isinstance(jobs_list, list) and jobs_list:
                logger.info(f"[{self.source_name}] Recibidas {len(jobs_list)} ofertas crudas.")
                for job_data in jobs_list:
                    oferta = self._normalize_job(job_data)
                    if oferta:
                        all_job_offers.append(oferta)
            elif isinstance(jobs_list, list):
                logger.info(f"[{self.source_name}] API Jobicy devolvió 0 ofertas.")
            else:
                logger.error(f"[{self.source_name}] Respuesta JSON no contiene lista 'jobs'.")
        except json.JSONDecodeError as e:
            logger.error(f"[{self.source_name}] Error decodificando JSON: {e}.")
        except Exception as e:
            logger.exception(f"[{self.source_name}] Error inesperado procesando API: {e}")

        logger.info(f"[{self.source_name}] Búsqueda API finalizada. {len(all_job_offers)} ofertas.")
        return all_job_offers
