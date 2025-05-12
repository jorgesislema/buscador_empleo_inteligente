# -*- coding: utf-8 -*-
# /src/apis/adzuna_client.py

"""
Cliente API específico para Adzuna.
(Versión con lógica multi-país OK, pero REQUIERE VERIFICACIÓN DE KEYS JSON)
"""

import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from urllib.parse import urljoin

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
        def __init__(self, source_name, config): self.source_name=source_name; self.base_url=config.get('base_url'); pass
        def _get_api_key(self): return None
    class HTTPClient: pass
    class config_loader:
        @staticmethod
        def get_secret(key, default=None): return default
        def get_secret(default=None): return default
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

    def _normalize_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convierte datos API Adzuna a formato estándar.
        """
        if not job_data or not isinstance(job_data, dict): return None
        oferta = self.get_standard_job_dict()

        # Mapeo corregido basado en la documentación de Adzuna API
        oferta['titulo'] = job_data.get('title')
        oferta['empresa'] = job_data.get('company', {}).get('display_name')
        location_info = job_data.get('location', {})
        oferta['ubicacion'] = location_info.get('display_name')
        oferta['fecha_publicacion'] = self._parse_adzuna_date(job_data.get('created'))
        oferta['url'] = job_data.get('redirect_url')
        oferta['descripcion'] = job_data.get('description')
        sal_min = job_data.get('salary_min')
        sal_max = job_data.get('salary_max')
        
        if sal_min and sal_max: oferta['salario'] = f"{sal_min} - {sal_max}"
        elif sal_min: oferta['salario'] = f"Desde {sal_min}"
        elif sal_max: oferta['salario'] = f"Hasta {sal_max}"
        else: oferta['salario'] = None

        extra_info = []
        ct = job_data.get('contract_time')
        if ct: extra_info.append(f"Tipo: {ct}")
        cty = job_data.get('contract_type')
        if cty: extra_info.append(f"Contrato: {cty}")
        cat = job_data.get('category', {}).get('label')
        if cat: extra_info.append(f"Categoría: {cat}")
        if extra_info: oferta['descripcion'] = (oferta['descripcion'] or "") + "\n\n[" + " | ".join(extra_info) + "]"

        # Solo devolvemos la oferta si pudimos extraer lo mínimo (título y url)
        if oferta['titulo'] and oferta['url']:
             return oferta
        else:
            logger.warning(f"[{self.source_name}] Oferta API Adzuna omitida (sin título/URL). ID: {job_data.get('id', 'N/A')}")
            return None

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """ Obtiene trabajos desde Adzuna, iterando por países soportados."""
        if not self.credentials_valid: logger.error(f"[{self.source_name}] Credenciales inválidas."); return []

        logger.info(f"[{self.source_name}] Iniciando búsqueda API multi-país Adzuna...")
        all_job_offers = []
        keywords = search_params.get('keywords', [])
        location = search_params.get('location')

        # Usar solo los primeros 5 keywords para evitar búsquedas demasiado restrictivas
        if keywords and len(keywords) > 5:
            keywords = keywords[:5]
            logger.info(f"[{self.source_name}] Limitando a 5 keywords para búsqueda: {keywords}")

        try:
            config = config_loader.get_config() or {}
            locations_config = [location] if location else (config.get('locations', []) or [])
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
                
                # Construir el parámetro 'what' de manera más simple y con menos restricciones
                what_param = ' '.join(keywords[:3]) if keywords else "python data"
                
                params = {
                    'app_id': self.app_id, 
                    'app_key': self.app_key,
                    'results_per_page': self.results_per_page,
                    'what': what_param,
                    'content-type': 'application/json'
                }
                
                # Solo agregar el parámetro 'where' si no es para búsqueda global/remota
                if where_param and where_param.lower() not in ['remote', 'remoto', 'global', 'anywhere']:
                    params['where'] = where_param
                    
                params = {k: v for k, v in params.items() if v}
                logger.debug(f"[{self.source_name}][{country_code}] GET {api_url} | Params (sin keys): { {k:v for k,v in params.items() if k not in ['app_id','app_key']} }")

                # Agregar headers específicos para Adzuna
                headers = {
                    'Accept': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
                }
                
                response = self.http_client.get(api_url, params=params, headers=headers)

                if not response or response.status_code != 200:
                    if response: # Loguear error si hubo respuesta pero no fue 200
                         if response.status_code == 404: logger.error(f"[{self.source_name}][{country_code}] Error 404 - Endpoint no encontrado para '{country_code}'.")
                         elif response.status_code in [401, 403]: logger.error(f"[{self.source_name}][{country_code}] Error Auth ({response.status_code}).")
                         else: logger.error(f"[{self.source_name}][{country_code}] Error API ({response.status_code}) pág {current_page}.")
                    else: # Si no hubo respuesta del http_client
                         logger.error(f"[{self.source_name}][{country_code}] No hubo respuesta para pág {current_page}.")
                    break # Siguiente país

                try:
                    # Verificar el tamaño y contenido de la respuesta para diagnóstico
                    response_size = len(response.text)
                    if response_size < 100:
                        logger.warning(f"[{self.source_name}][{country_code}] Respuesta muy pequeña ({response_size} bytes): {response.text}")
                        
                    api_data = response.json()
                    
                    # Verificar si hay mensajes de error en la respuesta
                    if "error" in api_data:
                        error_msg = api_data.get("error", {}).get("message", "Sin detalles")
                        logger.error(f"[{self.source_name}][{country_code}] Error en respuesta API: {error_msg}")
                        break
                    
                    jobs_list = api_data.get('results')

                    if jobs_list and isinstance(jobs_list, list):
                        logger.info(f"[{self.source_name}][{country_code}] {len(jobs_list)} ofertas crudas (pág {current_page}).")
                        found_new = 0
                        for job_data in jobs_list:
                            oferta = self._normalize_job(job_data)
                            if oferta: all_job_offers.append(oferta); found_new += 1
                        if found_new == 0 and len(jobs_list)>0:
                             logger.warning(f"[{self.source_name}][{country_code}] Recibidas {len(jobs_list)} ofertas pero NINGUNA normalizada.")
                             break # Probable error de mapeo, no seguir con este país
                        elif found_new == 0:
                             logger.info(f"[{self.source_name}][{country_code}] No ofertas válidas/nuevas pág {current_page}. Fin país.")
                             break
                    elif isinstance(jobs_list, list) and not jobs_list:
                         logger.info(f"[{self.source_name}][{country_code}] 0 ofertas pág {current_page}. Fin país.")
                         break
                    else:
                         logger.error(f"[{self.source_name}][{country_code}] Respuesta JSON Adzuna no contiene lista en la clave esperada ('results').")
                         logger.debug(f"[{self.source_name}][{country_code}] Claves disponibles en respuesta: {list(api_data.keys())}")
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