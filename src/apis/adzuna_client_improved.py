# -*- coding: utf-8 -*-
# /src/apis/adzuna_client_improved.py

"""
Cliente API mejorado para Adzuna con:
- Soporte para múltiples países automático
- Mejor manejo de errores
- Reintentos inteligentes
- Rotación de credenciales
"""

import logging
import random
import time
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from urllib.parse import urljoin

# Intentar importar el cliente HTTP mejorado
try:
    from src.utils.http_client_improved import ImprovedHTTPClient as HTTPClient
    IMPROVED_HTTP_CLIENT_AVAILABLE = True
except ImportError:
    from src.utils.http_client import HTTPClient
    IMPROVED_HTTP_CLIENT_AVAILABLE = False

# Importaciones principales
try:
    from src.apis.base_api import BaseAPIClient
    from src.utils import config_loader
    
    # Importar error_handler si está disponible
    try:
        from src.utils.error_handler import register_error, retry_on_failure
        ERROR_HANDLER_AVAILABLE = True
    except ImportError:
        ERROR_HANDLER_AVAILABLE = False
        # Funciones dummy si no está disponible
        def register_error(*args, **kwargs): pass
        def retry_on_failure(max_retries=3, base_delay=1):
            def decorator(func):
                return func
            return decorator
except ImportError as e:
    logging.basicConfig(level=logging.WARNING)
    logging.warning(f"Fallo al importar módulos de src en adzuna_client_improved: {e}")
    # Stubs para permitir la carga del módulo
    class BaseAPIClient:
        def __init__(self, source_name, http_client, config): 
            self.source_name=source_name
            self.base_url=config.get('base_url') if config else None
    class config_loader:
        @staticmethod
        def get_secret(key, default=None): return default
        def get_config(): return {}

logger = logging.getLogger(__name__)
MAX_PAGES_PER_COUNTRY = 10  # Aumentado de 5 a 10 para obtener más resultados

class AdzunaClientImproved(BaseAPIClient):
    """
    Cliente API Adzuna mejorado con soporte para múltiples países,
    rotación de credenciales y mejor manejo de errores.
    """
    DEFAULT_BASE_API_URL = "https://api.adzuna.com/v1/api/jobs/"
    SUPPORTED_COUNTRIES: Set[str] = {
        'at', 'au', 'be', 'br', 'ca', 'ch', 'de', 'es', 'fr', 'gb',
        'in', 'it', 'mx', 'nl', 'nz', 'pl', 'sg', 'ru', 'us', 'za'
    }
    
    # Países priorizados para búsqueda remota de software
    PRIORITY_COUNTRIES_TECH = ['us', 'gb', 'ca', 'de', 'es', 'fr', 'it', 'au', 'nl']
    
    # Dominios de correo comunes para tech jobs
    TECH_EMAIL_DOMAINS = ['gmail.com', 'hotmail.com', 'yahoo.com', 'outlook.com']

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador del cliente API Adzuna mejorado.
        
        Args:
            http_client: Cliente HTTP para realizar peticiones
            config: Configuración específica para este cliente
        """
        super().__init__(source_name="adzuna", http_client=http_client, config=config)
        
        # Intentar obtener múltiples credenciales
        self.credentials = self._load_all_credentials()
        
        if not self.credentials:
            logger.error(f"[{self.source_name}] ¡No se encontraron credenciales válidas para Adzuna!")
        else:
            logger.info(f"[{self.source_name}] Se cargaron {len(self.credentials)} conjuntos de credenciales")
        
        # Países disponibles para buscar (por defecto, todos los soportados)
        self.countries_to_search = self._get_countries_to_search()
        
        # Estadísticas
        self.stats = {
            "requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "countries_queried": set(),
            "jobs_found": 0
        }
    
    def _load_all_credentials(self) -> List[Dict[str, str]]:
        """
        Carga todas las credenciales disponibles para Adzuna.
        
        Returns:
            Lista de diccionarios con app_id y app_key
        """
        credentials = []
        
        # Intentar primero con el formato estándar
        app_id = self._get_api_key("_APP_ID")
        app_key = self._get_api_key("_APP_KEY")
        
        if app_id and app_key:
            credentials.append({"app_id": app_id, "app_key": app_key})
        
        # Intentar con credenciales numeradas (para rotación)
        for i in range(1, 6):  # Buscar hasta 5 conjuntos de credenciales
            app_id = self._get_api_key(f"_APP_ID_{i}")
            app_key = self._get_api_key(f"_APP_KEY_{i}")
            
            if app_id and app_key:
                credentials.append({"app_id": app_id, "app_key": app_key})
        
        return credentials
    
    def _get_countries_to_search(self) -> List[str]:
        """
        Determina qué países buscar basados en la configuración.
        
        Returns:
            Lista de códigos de país para buscar
        """
        # Si la configuración especifica países, usarlos
        if self.config and 'countries' in self.config:
            countries = [c.lower() for c in self.config['countries'] if c.lower() in self.SUPPORTED_COUNTRIES]
            if countries:
                logger.info(f"[{self.source_name}] Usando países específicos de config: {countries}")
                return countries
        
        # Buscar en ubicaciones configuradas
        locations = config_loader.get_config().get('locations', [])
        if locations:
            # Extraer códigos de país a partir de las ubicaciones
            possible_countries = []
            
            for location in locations:
                # Si parece un código de país de 2 letras
                if isinstance(location, str) and len(location) == 2 and location.lower() in self.SUPPORTED_COUNTRIES:
                    possible_countries.append(location.lower())
                # Intentar extraer el país de una ubicación como "Ciudad, PAIS"
                elif isinstance(location, str) and ',' in location:
                    country_part = location.split(',')[-1].strip().lower()
                    if len(country_part) == 2 and country_part in self.SUPPORTED_COUNTRIES:
                        possible_countries.append(country_part)
                    # Manejar nombres completos de países comunes
                    elif 'spain' in country_part.lower() or 'españa' in country_part.lower():
                        possible_countries.append('es')
                    elif 'united states' in country_part.lower() or 'usa' in country_part.lower():
                        possible_countries.append('us')
                    elif 'united kingdom' in country_part.lower() or 'uk' in country_part.lower():
                        possible_countries.append('gb')
            
            if possible_countries:
                logger.info(f"[{self.source_name}] Países detectados de las ubicaciones: {possible_countries}")
                return list(set(possible_countries))
        
        # Si no hay países específicos, usar una selección inteligente
        # Verificar si las keywords indican búsqueda de trabajo tech/remoto
        config = config_loader.get_config()
        keywords = (config.get('job_titles', []) or []) + (config.get('tools_technologies', []) or [])
        
        tech_terms = ['developer', 'software', 'data', 'engineer', 'remote', 'python', 'javascript']
        is_tech_search = any(term.lower() in ' '.join(keywords).lower() for term in tech_terms)
        
        if is_tech_search:
            # Para búsquedas tech, priorizar países con más jobs remotos
            logger.info(f"[{self.source_name}] Detectada búsqueda tecnológica, usando países tech prioritarios")
            return self.PRIORITY_COUNTRIES_TECH
        
        # De lo contrario, usar un conjunto predeterminado más pequeño para ahorrar llamadas API
        default_countries = ['us', 'gb', 'es', 'mx', 'de', 'fr']
        logger.info(f"[{self.source_name}] Usando países predeterminados: {default_countries}")
        return default_countries
    
    def _get_api_key(self, key_suffix: str) -> Optional[str]:
        """
        Obtiene una clave API de las variables de entorno o config.
        
        Args:
            key_suffix: Sufijo para la clave (e.g., "_APP_ID", "_APP_KEY")
            
        Returns:
            Valor de la clave o None si no se encuentra
        """
        # Intentar primero config específica
        if self.config and f"app{key_suffix.lower()}" in self.config:
            return self.config[f"app{key_suffix.lower()}"]
        
        # Luego, intentar obtener de secrets
        key_name = f"ADZUNA{key_suffix}"
        key_value = config_loader.get_secret(key_name)
        
        if key_value:
            return key_value
        
        # Finalmente, intentar variaciones en config general
        general_config = config_loader.get_config() or {}
        api_keys = general_config.get('api_keys', {})
        
        if api_keys and f"adzuna{key_suffix.lower()}" in api_keys:
            return api_keys[f"adzuna{key_suffix.lower()}"]
        
        if api_keys and f"ADZUNA{key_suffix}" in api_keys:
            return api_keys[f"ADZUNA{key_suffix}"]
            
        return None
    
    def _get_credential_pair(self) -> Optional[Dict[str, str]]:
        """
        Obtiene un par de credenciales rotando entre los disponibles.
        
        Returns:
            Diccionario con app_id y app_key, o None si no hay credenciales
        """
        if not self.credentials:
            return None
        
        # Seleccionar credenciales al azar para distribución de carga
        return random.choice(self.credentials)
    
    @retry_on_failure(max_retries=3, base_delay=2)
    def _make_api_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Realiza una petición a la API de Adzuna con reintentos.
        
        Args:
            endpoint: Endpoint relativo a llamar
            params: Parámetros de consulta
            
        Returns:
            Respuesta JSON como diccionario
            
        Raises:
            Exception: Si hay error en la petición después de los reintentos
        """
        self.stats["requests"] += 1
        credentials = self._get_credential_pair()
        
        if not credentials:
            msg = f"[{self.source_name}] No hay credenciales disponibles para realizar petición"
            logger.error(msg)
            register_error('api_error', self.source_name, msg)
            raise Exception(msg)
        
        # Construir URL completa
        url = urljoin(self.base_url, endpoint)
        
        # Añadir credenciales a parámetros
        params.update({
            "app_id": credentials["app_id"],
            "app_key": credentials["app_key"],
        })
        
        try:
            response = self.http_client.get(url, params=params)
            self.stats["successful_requests"] += 1
            return response.json()
        except Exception as e:
            self.stats["failed_requests"] += 1
            msg = f"[{self.source_name}] Error en petición a {url}: {str(e)}"
            logger.error(msg)
            register_error('api_request_error', self.source_name, msg)
            raise
    
    def _search_jobs_in_country(self, country_code: str, keywords: List[str], location: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Busca ofertas en un país específico.
        
        Args:
            country_code: Código de país de 2 letras
            keywords: Lista de palabras clave para buscar
            location: Ubicación específica dentro del país
            
        Returns:
            Lista de ofertas de trabajo encontradas
        """
        if country_code not in self.SUPPORTED_COUNTRIES:
            logger.warning(f"[{self.source_name}] País no soportado: {country_code}")
            return []
        
        all_jobs = []
        endpoint = f"{country_code}/search/1"
        
        # Crear query de búsqueda combinando keywords
        what = ' '.join(keywords) if keywords else None
        
        # Parámetros base
        params = {
            "results_per_page": 50,
            "sort_by": "date",
            "full_time": 1,  # Preferir full-time jobs
            "content-type": "application/json"
        }
        
        # Añadir parámetros condicionales
        if what:
            params["what"] = what
        
        if location:
            params["where"] = location
        
        try:
            # Primera página
            logger.info(f"[{self.source_name}] Buscando en país {country_code}, keywords: {what}, location: {location}")
            response = self._make_api_request(endpoint, params)
            
            # Obtener número total de páginas (limitado a nuestro máximo)
            total_count = response.get("count", 0)
            if total_count == 0:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en {country_code}")
                return []
            
            total_pages = min(MAX_PAGES_PER_COUNTRY, (total_count // 50) + 1)
            
            # Procesar primera página
            jobs_page_1 = self._parse_jobs(response, country_code)
            all_jobs.extend(jobs_page_1)
            
            logger.info(f"[{self.source_name}] Encontradas {len(jobs_page_1)} ofertas en página 1/{total_pages} para {country_code}")
            
            # Obtener páginas adicionales
            for page in range(2, total_pages + 1):
                try:
                    # Delay entre peticiones para evitar throttling
                    time.sleep(random.uniform(1.0, 2.0))
                    
                    page_endpoint = f"{country_code}/search/{page}"
                    page_response = self._make_api_request(page_endpoint, params)
                    jobs_page = self._parse_jobs(page_response, country_code)
                    
                    logger.info(f"[{self.source_name}] Encontradas {len(jobs_page)} ofertas en página {page}/{total_pages} para {country_code}")
                    
                    all_jobs.extend(jobs_page)
                    
                    # Si obtuvimos pocas ofertas (menos de 5), asumimos que ya no hay más y paramos
                    if len(jobs_page) < 5:
                        logger.info(f"[{self.source_name}] Pocas ofertas en página {page}, deteniendo paginación para {country_code}")
                        break
                        
                except Exception as e:
                    logger.error(f"[{self.source_name}] Error obteniendo página {page} para {country_code}: {str(e)}")
                    register_error('pagination_error', self.source_name, f"Error en país {country_code}, página {page}: {str(e)}")
                    # Continuar con la siguiente página en caso de error
            
            self.stats["countries_queried"].add(country_code)
            self.stats["jobs_found"] += len(all_jobs)
            
            logger.info(f"[{self.source_name}] Total de {len(all_jobs)} ofertas encontradas en {country_code}")
            return all_jobs
            
        except Exception as e:
            logger.error(f"[{self.source_name}] Error buscando en país {country_code}: {str(e)}")
            register_error('country_search_error', self.source_name, f"Error en país {country_code}: {str(e)}")
            return []
    
    def _parse_jobs(self, response: Dict[str, Any], country_code: str) -> List[Dict[str, Any]]:
        """
        Analiza la respuesta de la API y extrae las ofertas de trabajo.
        
        Args:
            response: Respuesta JSON de la API
            country_code: Código del país de donde provienen los datos
            
        Returns:
            Lista de ofertas de trabajo procesadas
        """
        jobs = []
        
        # Verificar si hay resultados
        if not response or "results" not in response:
            return jobs
        
        for job_data in response.get("results", []):
            try:
                # Extraer datos básicos
                job_id = job_data.get("id")
                title = job_data.get("title", "").strip()
                description = job_data.get("description", "").strip()
                url = job_data.get("redirect_url")
                company = job_data.get("company", {}).get("display_name", "").strip()
                location = job_data.get("location", {}).get("display_name", "")
                
                # Fecha de publicación
                created_timestamp = job_data.get("created")
                if created_timestamp:
                    created_date = datetime.fromtimestamp(created_timestamp).strftime("%Y-%m-%d")
                else:
                    created_date = None
                
                # Salario si está disponible
                salary_min = job_data.get("salary_min")
                salary_max = job_data.get("salary_max")
                salary_currency = job_data.get("salary_currency", "")
                
                salary_text = ""
                if salary_min and salary_max:
                    salary_text = f"{salary_min:,.0f} - {salary_max:,.0f} {salary_currency}"
                elif salary_min:
                    salary_text = f"{salary_min:,.0f}+ {salary_currency}"
                elif salary_max:
                    salary_text = f"Hasta {salary_max:,.0f} {salary_currency}"
                
                # Modalidad de trabajo (intentar detectar remoto por palabras clave)
                is_remote = False
                if description and ("remote" in description.lower() or "remoto" in description.lower() or 
                                   "home" in description.lower() or "teletrabajo" in description.lower()):
                    is_remote = True
                
                remote_tags = job_data.get("category", {}).get("tag", [])
                if "remote" in [tag.lower() for tag in remote_tags]:
                    is_remote = True
                
                # Categoría de trabajo
                category = job_data.get("category", {}).get("label", "")
                
                # Construir objeto de trabajo
                job = {
                    "titulo": title,
                    "empresa": company,
                    "ubicacion": f"{location}, {country_code.upper()}" if location else country_code.upper(),
                    "url": url,
                    "fuente": self.source_name,
                    "fecha_publicacion": created_date,
                    "descripcion": description,
                    "id": f"adzuna_{country_code}_{job_id}" if job_id else None,
                    "modalidad": "Remoto" if is_remote else "Presencial",
                    "salario": salary_text if salary_text else None,
                    "categoria": category,
                    "pais": country_code.upper()
                }
                
                jobs.append(job)
                
            except Exception as e:
                logger.error(f"[{self.source_name}] Error procesando oferta: {str(e)}")
                register_error('job_parsing_error', self.source_name, str(e))
                # Continuar con la siguiente oferta en caso de error
        
        return jobs
    
    def fetch_jobs(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Obtiene ofertas de trabajo usando los parámetros proporcionados.
        
        Args:
            params: Parámetros para la búsqueda de ofertas
            
        Returns:
            Lista de ofertas de trabajo
        """
        all_jobs = []
        
        if not self.credentials:
            logger.error(f"[{self.source_name}] No hay credenciales de API disponibles")
            return all_jobs
        
        # Inicializar la URL base si aún no está establecida
        if not self.base_url:
            self.base_url = self.DEFAULT_BASE_API_URL
        
        # Extraer parámetros
        keywords = params.get("keywords", [])
        location = params.get("location")
        
        # Si no hay keywords, no podemos buscar
        if not keywords:
            logger.warning(f"[{self.source_name}] No se proporcionaron palabras clave para la búsqueda")
            return all_jobs
        
        logger.info(f"[{self.source_name}] Iniciando búsqueda en {len(self.countries_to_search)} países")
        
        # Buscar en cada país
        for country_code in self.countries_to_search:
            try:
                country_jobs = self._search_jobs_in_country(country_code, keywords, location)
                all_jobs.extend(country_jobs)
                
                # Si ya tenemos muchas ofertas, podemos parar para ahorrar llamadas a la API
                if len(all_jobs) >= 200:
                    logger.info(f"[{self.source_name}] Alcanzado límite de ofertas (200), deteniendo búsqueda")
                    break
                
                # Pausa entre países para evitar throttling
                if country_code != self.countries_to_search[-1]:  # No esperar después del último país
                    time.sleep(random.uniform(1.5, 3.0))
                    
            except Exception as e:
                logger.error(f"[{self.source_name}] Error en búsqueda para país {country_code}: {str(e)}")
                register_error('country_error', self.source_name, f"Error en país {country_code}: {str(e)}")
                # Continuar con el siguiente país en caso de error
        
        # Registrar estadísticas finales
        total_countries_queried = len(self.stats["countries_queried"])
        logger.info(f"[{self.source_name}] Búsqueda completada en {total_countries_queried} países")
        logger.info(f"[{self.source_name}] Estadísticas: {self.stats['requests']} peticiones, "
                  f"{self.stats['successful_requests']} exitosas, {self.stats['failed_requests']} fallidas")
        logger.info(f"[{self.source_name}] Total de ofertas encontradas: {len(all_jobs)}")
        
        return all_jobs
