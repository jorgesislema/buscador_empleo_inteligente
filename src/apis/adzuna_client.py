# -*- coding: utf-8 -*-
# /src/apis/adzuna_client.py

"""
Cliente API específico para Adzuna.

Hereda de BaseAPIClient y se comunica con la API REST de Adzuna
para obtener ofertas de empleo agregadas de múltiples fuentes.
¡Este sí requiere App ID y App Key para funcionar!
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from urllib.parse import quote_plus

try:
    from src.apis.base_api import BaseAPIClient
    from src.utils.http_client import HTTPClient
    from src.utils import config_loader
except ImportError:
    logging.warning("Fallo al importar módulos de src. Asumiendo ejecución aislada.")
    class BaseAPIClient: pass
    class HTTPClient: pass
    class config_loader:
        @staticmethod
        def get_secret(key, default=None): return None

logger = logging.getLogger(__name__)
MAX_PAGES_TO_FETCH_ADZUNA = 5

class AdzunaClient(BaseAPIClient):
    DEFAULT_BASE_API_URL = "https://api.adzuna.com/v1/api/jobs/"

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="adzuna", http_client=http_client, config=config)
        self.app_id = self._get_api_key("_APP_ID")
        self.app_key = self._get_api_key("_APP_KEY")
        self.credentials_valid = bool(self.app_id and self.app_key)

        if not self.credentials_valid:
            logger.error(f"[{self.source_name}] ¡Credenciales (APP_ID o APP_KEY) no encontradas en .env!")
        else:
            logger.info(f"[{self.source_name}] Credenciales cargadas correctamente.")

        self.base_api_url = self.config.get('base_api_url', self.DEFAULT_BASE_API_URL).rstrip('/')
        self.results_per_page = self.config.get('results_per_page', 50)

    def _parse_adzuna_date(self, date_str_iso: Optional[str]) -> Optional[str]:
        if not date_str_iso:
            return None
        try:
            dt_object = datetime.fromisoformat(date_str_iso.replace('Z', '+00:00'))
            return dt_object.strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"[{self.source_name}] Error parseando fecha Adzuna '{date_str_iso}': {e}")
            return None

    def _get_country_code(self, location: str) -> str:
        loc_lower = location.lower() if location else ""
        if 'ecuador' in loc_lower or 'quito' in loc_lower or 'guayaquil' in loc_lower:
            return 'ec'
        elif 'españa' in loc_lower or 'spain' in loc_lower:
            return 'es'
        elif 'mexico' in loc_lower or 'méxico' in loc_lower:
            return 'mx'
        elif 'colombia' in loc_lower:
            return 'co'
        elif 'peru' in loc_lower or 'perú' in loc_lower:
            return 'pe'
        elif 'argentina' in loc_lower:
            return 'ar'
        elif 'chile' in loc_lower:
            return 'cl'
        elif 'usa' in loc_lower or 'estados unidos' in loc_lower:
            return 'us'
        elif 'canada' in loc_lower:
            return 'ca'
        else:
            return self.config.get('default_country_code', 'gb')

    def _normalize_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not job_data or not isinstance(job_data, dict):
            return None

        oferta = self.get_standard_job_dict()
        oferta['titulo'] = job_data.get('title')
        oferta['empresa'] = job_data.get('company', {}).get('display_name')
        location_info = job_data.get('location', {})
        oferta['ubicacion'] = location_info.get('display_name')
        oferta['fecha_publicacion'] = self._parse_adzuna_date(job_data.get('created'))
        oferta['url'] = job_data.get('redirect_url')
        oferta['descripcion'] = job_data.get('description')

        sal_min = job_data.get('salary_min')
        sal_max = job_data.get('salary_max')
        if sal_min and sal_max:
            oferta['salario'] = f"{sal_min} - {sal_max}"
        elif sal_min:
            oferta['salario'] = f"Desde {sal_min}"
        elif sal_max:
            oferta['salario'] = f"Hasta {sal_max}"

        extra_info = []
        contract_time = job_data.get('contract_time')
        if contract_time:
            extra_info.append(f"Tipo: {contract_time}")
        contract_type = job_data.get('contract_type')
        if contract_type:
            extra_info.append(f"Contrato: {contract_type}")
        category = job_data.get('category', {}).get('label')
        if category:
            extra_info.append(f"Categoría: {category}")

        if extra_info:
            oferta['descripcion'] = (oferta['descripcion'] or "") + "\n\n[" + " | ".join(extra_info) + "]"

        if oferta['titulo'] and oferta['url']:
            return oferta
        else:
            logger.warning(f"[{self.source_name}] Oferta omitida por falta de título o URL. ID: {job_data.get('id', 'N/A')}")
            return None

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not self.credentials_valid:
            logger.error(f"[{self.source_name}] Credenciales inválidas. No se puede hacer la búsqueda.")
            return []

        logger.info(f"[{self.source_name}] Iniciando búsqueda con parámetros: {search_params}")
        all_job_offers = []
        current_page = 1

        keywords = search_params.get('keywords', [])
        location = search_params.get('location', 'Quito, Ecuador')
        country_code = self._get_country_code(location)

        while current_page <= MAX_PAGES_TO_FETCH_ADZUNA:
            logger.info(f"[{self.source_name}] Procesando página {current_page} para país '{country_code}'...")
            api_url = f"{self.base_api_url}/{country_code}/search/{current_page}"

            params = {
                'app_id': self.app_id,
                'app_key': self.app_key,
                'results_per_page': self.results_per_page,
                'what': ' '.join(keywords),
                'where': location,
                'content-type': 'application/json'
            }

            response = self.http_client.get(api_url, params=params)

            if not response:
                logger.error(f"[{self.source_name}] Sin respuesta para página {current_page}.")
                break
            if response.status_code in [401, 403]:
                logger.error(f"[{self.source_name}] Error de autenticación ({response.status_code}).")
                break
            if response.status_code != 200:
                logger.error(f"[{self.source_name}] Error {response.status_code} en página {current_page}.")
                break

            try:
                api_data = response.json()
                jobs_list = api_data.get('results')
                if not jobs_list:
                    logger.info(f"[{self.source_name}] Página {current_page} sin resultados.")
                    break

                for job_data in jobs_list:
                    oferta = self._normalize_job(job_data)
                    if oferta:
                        all_job_offers.append(oferta)

            except Exception as e:
                logger.error(f"[{self.source_name}] Error procesando respuesta JSON: {e}")
                break

            current_page += 1

        logger.info(f"[{self.source_name}] Búsqueda finalizada. {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers
