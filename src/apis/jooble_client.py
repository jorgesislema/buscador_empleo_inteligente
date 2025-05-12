# -*- coding: utf-8 -*-
# /src/apis/jooble_client.py

"""
Cliente API específico para Jooble.

Se conecta vía POST a la API de Jooble usando una API Key. Normaliza las ofertas para nuestro esquema común.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import requests

from src.apis.base_api import BaseAPIClient
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)

class JoobleClient(BaseAPIClient):
    API_BASE_URL = "https://jooble.org/api/"

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="jooble", http_client=http_client, config=config)
        self.api_key = self._get_api_key("JOOBLE_API_KEY")
        self.api_endpoint = f"{self.API_BASE_URL.rstrip('/')}/{self.api_key}" if self.api_key else None
        if not self.api_key:
            logger.error(f"[{self.source_name}] API Key no encontrada. Configura JOOBLE_API_KEY en .env")

    def _parse_jooble_date(self, date_str: Optional[str]) -> Optional[str]:
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"[{self.source_name}] Fecha no reconocida: '{date_str}'. Error: {e}")
            return None

    def _normalize_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not job_data:
            return None

        oferta = {
            'titulo': None,
            'empresa': None,
            'ubicacion': None,
            'descripcion': None,
            'fecha_publicacion': None,
            'url': None,
            'salario': None
        }
        oferta['titulo'] = job_data.get('title')
        oferta['empresa'] = job_data.get('company')
        oferta['ubicacion'] = job_data.get('location')
        oferta['descripcion'] = job_data.get('snippet')
        oferta['fecha_publicacion'] = self._parse_jooble_date(job_data.get('updated') or job_data.get('date'))
        oferta['url'] = job_data.get('link')
        oferta['salario'] = job_data.get('salary')

        job_type = job_data.get('type')
        if job_type:
            oferta['descripcion'] = (oferta['descripcion'] or "") + f"\nTipo: {job_type}"

        if oferta['titulo'] and oferta['url']:
            return oferta
        logger.warning(f"[{self.source_name}] Oferta omitida por faltar título o URL. ID: {job_data.get('id', 'N/A')}")
        return None

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not self.api_endpoint:
            logger.error(f"[{self.source_name}] No se puede buscar sin endpoint (falta API key).")
            return []

        logger.info(f"[{self.source_name}] Iniciando búsqueda con parámetros: {search_params}")
        payload = {
            'keywords': ' '.join(search_params.get('keywords', [])),
            'location': search_params.get('location', ''),
            'page': search_params.get('page', 1)
        }

        if not payload['keywords'] and not payload['location']:
            logger.error(f"[{self.source_name}] Debes especificar al menos 'keywords' o 'location'.")
            return []

        try:
            response = self.http_client.session.post(
                self.api_endpoint,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=self.http_client.default_timeout
            )

            if not response or response.status_code != 200:
                logger.error(f"[{self.source_name}] Error API {response.status_code if response else 'N/A'}: {response.text[:300]}")
                return []

            api_data = response.json()
            job_list = api_data.get('jobs')
            results = []
            if isinstance(job_list, list):
                for job in job_list:
                    normalizado = self._normalize_job(job)
                    if normalizado:
                        results.append(normalizado)
                logger.info(f"[{self.source_name}] {len(results)} ofertas normalizadas.")
                return results
            else:
                logger.error(f"[{self.source_name}] Respuesta inesperada: no contiene 'jobs'.")
                return []

        except requests.exceptions.RequestException as e:
            logger.error(f"[{self.source_name}] Error en llamada POST: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"[{self.source_name}] Error al parsear JSON: {e}")
        except Exception as e:
            logger.exception(f"[{self.source_name}] Error inesperado: {e}")
        return []


if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()
    client = JoobleClient(http_client=http_client)

    search_params = {
        'keywords': ['python', 'data'],
        'location': 'Ecuador'
    }

    print("\n--- Iniciando prueba de JoobleClient ---")
    ofertas = client.fetch_jobs(search_params)
    print(f"\nSe obtuvieron {len(ofertas)} ofertas.")

    if ofertas:
        pprint.pprint(ofertas[0])

    http_client.close()
