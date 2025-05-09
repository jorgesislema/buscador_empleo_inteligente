# -*- coding: utf-8 -*-
# /src/apis/adzuna_client.py

"""
Cliente API específico para Adzuna.
(Versión con lógica multi-país OK, pero REQUIERE VERIFICACIÓN DE KEYS JSON)
"""

import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import json
from urllib.parse import quote_plus, urljoin

# Importaciones y fallbacks... (igual que antes)
try:
    from src.apis.base_api import BaseAPIClient
    from src.utils.http_client import HTTPClient
    from src.utils import config_loader
except ImportError:
    logging.basicConfig(level=logging.WARNING)
    logging.warning("Fallo al importar módulos de src en adzuna_client...")
    # ... (stubs igual que antes) ...
    class BaseAPIClient:
        def __init__(self, source_name, http_client, config): self.source_name=source_name; self.base_url=config.get('base_url'); pass
        def _get_api_key(self, suffix): return None
        def get_standard_job_dict(self): return {'fuente': getattr(self, 'source_name', 'unknown')}
    class HTTPClient: pass
    class config_loader:
        @staticmethod
        def get_secret(key, default=None): return default
        @staticmethod
        def get_config(): return {}

logger = logging.getLogger(__name__)
MAX_PAGES_TO_FETCH_ADZUNA = 5 # Límite por país

class AdzunaClient(BaseAPIClient):
    """ Cliente API Adzuna (Multi-País Soportado) """
    DEFAULT_BASE_API_URL = "https://api.adzuna.com/v1/api/jobs/"
    SUPPORTED_COUNTRIES: Set[str] = {
        'at', 'au', 'be', 'br', 'ca', 'ch', 'de', 'es', 'fr', 'gb',
        'in', 'it', 'mx', 'nl', 'nz', 'pl', 'sg', 'us', 'za'
    }

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """ Inicializador del cliente API Adzuna. """
        super().__init__(source_name="adzuna", http_client=http_client, config=config)
        self.app_id = self._get_api_key("_APP_ID")
        self.app_key = self._get_api_key("_APP_KEY")
        self.credentials_valid = bool(self.app_id and self.app_key)
        if not self.credentials_valid: logger.error(f"[{self.source_name}] ¡Credenciales Adzuna no encontradas!")
        else: logger.info(f"[{self.source_name}] Credenciales Adzuna cargadas.")
        self.base_api_url = self.config.get('base_api_url', self.DEFAULT_BASE_API_URL).rstrip('/')
        self.results_per_page = self.config.get('results_per_page', 50)
        logger.info(f"[{self.source_name}] Usando base API URL: {self.base_api_url}")
        logger.info(f"[{self.source_name}] Resultados por página: {self.results_per_page}")

    def _parse_adzuna_date(self, date_str_iso: Optional[str]) -> Optional[str]:
        """ Parsea fecha ISO 8601 a 'YYYY-MM-DD'. """
        if not date_str_iso: return None
        try:
            dt_object = datetime.fromisoformat(date_str_iso.replace('Z', '+00:00'))
            return dt_object.strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"[{self.source_name}] No se pudo parsear fecha ISO '{date_str_iso}': {e}")
            return None

    def _get_target_countries(self, locations_config: List[str]) -> Set[str]:
        """ Determina códigos de país soportados a partir de ubicaciones. """
        # (Misma lógica que la versión anterior, que parecía funcionar bien para identificar países)
        location_map: Dict[str, Any] = {
            'españa': 'es', 'spain': 'es', 'madrid': 'es', 'barcelona': 'es',
            'mexico': 'mx', 'méxico': 'mx', 'usa': 'us', 'estados unidos': 'us',
            'north america': 'us', 'canada': 'ca', 'brasil': 'br',
            'reino unido': 'gb', 'uk': 'gb', 'francia': 'fr', 'alemania': 'de',
            'italia': 'it', 'austria': 'at', 'australia': 'au', 'belgica': 'be',
            'suiza': 'ch', 'india': 'in', 'paises bajos': 'nl', 'holanda': 'nl',
            'nueva zelanda': 'nz', 'polonia': 'pl', 'singapur': 'sg', 'sudafrica': 'za',
            'latam': ['mx','br'], # Solo soportados
            'global': ['us','gb','de','fr','ca','au','es','mx','br'] # Soportados
        }
        default_country = self.config.get('default_country_code', 'gb')
        target: Set[str] = set()
        found_specific = False
        locations_lower = {loc.lower().strip() for loc in locations_config if loc}
        for loc_config in locations_lower:
            for term, val in location_map.items():
                if term in loc_config:
                    codes = val if isinstance(val, list) else [val]
                    for c in codes:
                        if c in self.SUPPORTED_COUNTRIES:
                            target.add(c)
                            if term not in ['latam','global','remote','remoto','teletrabajo']: found_specific = True
                        else: logger.warning(f"[{self.source_name}] Código '{c}' (map={term}) no soportado.")
        if not target:
            if not found_specific:
                 if default_country in self.SUPPORTED_COUNTRIES: target.add(default_country); logger.warning(f"Sin match, usando default '{default_country}'.")
                 else: logger.error(f"Default '{default_country}' no soportado.")
            else: logger.error(f"Ubicaciones específicas no mapeadas a países soportados.")
        logger.info(f"[{self.source_name}] Países Adzuna objetivo determinados: {target or 'Ninguno'}")
        return target

    # --- ¡¡¡ ATENCIÓN AQUÍ !!! ---
    def _normalize_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convierte datos API Adzuna a formato estándar.
        ¡¡¡ VERIFICA LOS NOMBRES DE LAS CLAVES ('title', 'company', etc.)
        CON LA RESPUESTA REAL DE LA API DE ADZUNA !!!
        """
        if not job_data or not isinstance(job_data, dict): return None
        oferta = self.get_standard_job_dict()

        # --- Log para Depurar Respuesta Real ---
        # Descomenta la siguiente línea TEMPORALMENTE para ver qué trae job_data
        # logger.debug(f"ADZUNA RAW JOB DATA: {job_data}")
        # --- Fin Log Depuración ---

        # Mapeo (¡VERIFICAR ESTAS KEYS!)
        oferta['titulo'] = job_data.get('title')                            # <-- ¿Se llama así?
        oferta['empresa'] = job_data.get('company', {}).get('display_name') # <-- ¿Son estas?
        location_info = job_data.get('location', {})                       # <-- ¿Es 'location'?
        oferta['ubicacion'] = location_info.get('display_name')             # <-- ¿Es 'display_name'?
        oferta['fecha_publicacion'] = self._parse_adzuna_date(job_data.get('created')) # <-- ¿Es 'created'?
        oferta['url'] = job_data.get('redirect_url')                        # <-- ¿Es 'redirect_url'?
        oferta['descripcion'] = job_data.get('description')                 # <-- ¿Es 'description'? (Snippet)
        sal_min = job_data.get('salary_min'); sal_max = job_data.get('salary_max') # <-- ¿Son 'salary_min'/'salary_max'?
        if sal_min and sal_max: oferta['salario'] = f"{sal_min} - {sal_max}"
        elif sal_min: oferta['salario'] = f"Desde {sal_min}"
        elif sal_max: oferta['salario'] = f"Hasta {sal_max}"
        else: oferta['salario'] = None

        extra_info = []
        ct = job_data.get('contract_time'); # <-- ¿Es 'contract_time'?
        if ct: extra_info.append(f"Tipo: {ct}")
        cty = job_data.get('contract_type'); # <-- ¿Es 'contract_type'?
        if cty: extra_info.append(f"Contrato: {cty}")
        cat = job_data.get('category', {}).get('label'); # <-- ¿Son 'category' y 'label'?
        if cat: extra_info.append(f"Categoría: {cat}")
        if extra_info: oferta['descripcion'] = (oferta['descripcion'] or "") + "\n\n[" + " | ".join(extra_info) + "]"

        # Solo devolvemos la oferta si pudimos extraer lo mínimo (título y url)
        if oferta['titulo'] and oferta['url']:
             return oferta
        else:
            logger.warning(f"[{self.source_name}] Oferta API Adzuna omitida (sin título/URL). ID: {job_data.get('id', 'N/A')}") # <-- ¿Es 'id'?
            return None

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """ Obtiene trabajos desde Adzuna, iterando por países soportados."""
        if not self.credentials_valid: logger.error(f"[{self.source_name}] Credenciales inválidas."); return []

        logger.info(f"[{self.source_name}] Iniciando búsqueda API multi-país Adzuna...")
        all_job_offers = []
        keywords = search_params.get('keywords', [])
        try:
            config = config_loader.get_config() or {}
            locations_config = config.get('locations', []) or []
            if not locations_config: locations_config = [self.config.get('default_location', 'United Kingdom')]
        except Exception as e: logger.error(f"[{self.source_name}] Error cargando config: {e}"); return []

        target_countries = self._get_target_countries(locations_config)
        if not target_countries: logger.error(f"[{self.source_name}] No países Adzuna VÁLIDOS para buscar."); return []

        for country_code in target_countries:
            logger.info(f"--- [{self.source_name}] Buscando en país: {country_code} ---")
            current_page = 1
            while current_page <= MAX_PAGES_TO_FETCH_ADZUNA:
                logger.info(f"[{self.source_name}][{country_code}] Procesando página {current_page}...")
                api_url = f"{self.base_api_url}/{country_code}/search/{current_page}"
                where_param = locations_config[0] if locations_config else ""
                params = {
                    'app_id': self.app_id, 'app_key': self.app_key,
                    'results_per_page': self.results_per_page,
                    'what': ' '.join(keywords), 'where': where_param,
                    'content-type': 'application/json'
                }
                params = {k: v for k, v in params.items() if v}
                logger.debug(f"[{self.source_name}][{country_code}] GET {api_url} | Params (sin keys): { {k:v for k,v in params.items() if k not in ['app_id','app_key']} }")

                response = self.http_client.get(api_url, params=params)

                if not response or response.status_code != 200:
                    if response: # Loguear error si hubo respuesta pero no fue 200
                         if response.status_code == 404: logger.error(f"[{self.source_name}][{country_code}] Error 404 - Endpoint no encontrado para '{country_code}'.")
                         elif response.status_code in [401, 403]: logger.error(f"[{self.source_name}][{country_code}] Error Auth ({response.status_code}).")
                         else: logger.error(f"[{self.source_name}][{country_code}] Error API ({response.status_code}) pág {current_page}.")
                    else: # Si no hubo respuesta del http_client
                         logger.error(f"[{self.source_name}][{country_code}] No hubo respuesta para pág {current_page}.")
                    break # Siguiente país

                try:
                    api_data = response.json()
                    # --- ¡VERIFICAR ESTA CLAVE! ---
                    jobs_list = api_data.get('results') # <-- ¿Es realmente 'results'?
                    # --- FIN VERIFICACIÓN ---

                    if jobs_list and isinstance(jobs_list, list):
                        logger.info(f"[{self.source_name}][{country_code}] {len(jobs_list)} ofertas crudas (pág {current_page}).")
                        found_new = 0
                        for job_data in jobs_list:
                            oferta = self._normalize_job(job_data)
                            if oferta: all_job_offers.append(oferta); found_new += 1
                        if found_new == 0 and len(jobs_list)>0:
                             logger.warning(f"[{self.source_name}][{country_code}] Recibidas {len(jobs_list)} ofertas pero NINGUNA normalizada. ¡VERIFICA LAS CLAVES JSON EN _normalize_job!")
                             break # Probable error de mapeo, no seguir con este país
                        elif found_new == 0:
                             logger.info(f"[{self.source_name}][{country_code}] No ofertas válidas/nuevas pág {current_page}. Fin país.")
                             break
                    elif isinstance(jobs_list, list) and not jobs_list:
                         logger.info(f"[{self.source_name}][{country_code}] 0 ofertas pág {current_page}. Fin país.")
                         break
                    else:
                         logger.error(f"[{self.source_name}][{country_code}] Respuesta JSON Adzuna no contiene lista en la clave esperada ('results'?).")
                         break
                except Exception as e:
                    logger.exception(f"[{self.source_name}][{country_code}] Error procesando respuesta: {e}")
                    break
                current_page += 1
            # Fin while paginación país
            logger.info(f"--- [{self.source_name}] Búsqueda finalizada para: {country_code} ---")
        # Fin for países
        logger.info(f"[{self.source_name}] Búsqueda API multi-país finalizada. {len(all_job_offers)} ofertas totales.")
        return all_job_offers

# --- Ejemplo de uso ---
# (El bloque if __name__ == '__main__': es igual al anterior)
# ... (pegar bloque __main__ anterior, asegurando importar las clases necesarias) ...