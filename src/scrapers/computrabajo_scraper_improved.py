# -*- coding: utf-8 -*-
# /src/scrapers/computrabajo_scraper_improved.py

"""
Scraper mejorado para Computrabajo Ecuador (ec.computrabajo.com).
Mejoras implementadas:
- Manejo avanzado de errores
- Estrategias anti-bloqueo
- Extracción de más información de páginas de detalle
- Mejores selectores con fallbacks
- Procesamiento de información de salario y modalidad
- Reintentos inteligentes
"""

import logging
import re
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union, Tuple
from urllib.parse import quote_plus, urljoin
import sys

# Importaciones robustas
try:
    from src.scrapers.base_scraper import BaseScraper
    from src.utils.http_client import HTTPClient
    from src.utils import config_loader
    
    # Intentar importar componentes mejorados si están disponibles
    try:
        from src.utils.error_handler import register_error
        ERROR_HANDLER_AVAILABLE = True
    except ImportError:
        ERROR_HANDLER_AVAILABLE = False
        def register_error(*args, **kwargs): pass
except ImportError:
    logging.basicConfig(level=logging.WARNING)
    logging.warning("Fallo al importar módulos de src en computrabajo_scraper_improved. Usando stubs.")

    class BaseScraper:
        def __init__(self, source_name, http_client, config):
            self.source_name = source_name
            self.base_url = config.get('base_url') if config else None

        def _build_url(self, path):
            return urljoin(self.base_url or "", path) if path else None

        def _fetch_html(self, url, params=None, headers=None):
            logging.warning(f"[{self.source_name}] _fetch_html STUBBED: {url}")
            return None

        def _parse_html(self, html):
            logging.warning(f"[{self.source_name}] _parse_html STUBBED")
            return None

        def _safe_get_text(self, el):
            try:
                return el.get_text(strip=True)
            except:
                return None

        def _safe_get_attribute(self, el, attr):
            try:
                return el[attr]
            except:
                return None

        def get_standard_job_dict(self):
            return {'fuente': getattr(self, 'source_name', 'unknown')}

    class HTTPClient:
        pass

    class config_loader:
        @staticmethod
        def get_config(): return {}
        @staticmethod
        def get_secret(key, default=None): return default
    
    ERROR_HANDLER_AVAILABLE = False
    def register_error(*args, **kwargs): pass

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE = 10  # Aumentado de 5 en la versión original
MAX_KEYWORDS_IN_URL_COMPUTRABAJO = 5

# Headers para parecer más humano
HEADERS_VARIATIONS = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3",
        "Referer": "https://ec.computrabajo.com/",
        "DNT": "1",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
        "Referer": "https://www.google.com/",
        "DNT": "1",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3",
        "Referer": "https://ec.computrabajo.com/empresas",
        "DNT": "1",
    }
]

# Patrones para extraer información de salario
SALARY_PATTERNS = [
    r'(?:salario|sueldo)[:;.,\s]+\$\s*([0-9.,]+)\s*(?:mensuales?)?',
    r'\$\s*([0-9.,]+)\s*(?:mensuales?)?',
    r'([0-9.,]+)\s*dólares',
]

# Patrones para modalidad de trabajo
MODALITY_PATTERNS = [
    (r'(?:remoto|teletrabajo|home\s*office|trabajo\s*(?:desde|en)\s*casa)', 'Remoto'),
    (r'(?:hibrido|híbrido|semi\s*presencial)', 'Híbrido'),
    (r'(?:presencial|oficina)', 'Presencial')
]

class ComputrabajoScraperImproved(BaseScraper):
    """Scraper mejorado para Computrabajo Ecuador con anti-bloqueo y mejor extracción de datos"""

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="computrabajo", http_client=http_client, config=config or {})
        # Configuración de base_url con fallback
        self.base_url = (self.base_url or config.get('base_url', 'https://ec.computrabajo.com')).rstrip('/')
        logger.debug(f"[{self.source_name}] Base URL: {self.base_url}")
        
        # Mapa de sitios por país para mejor adaptabilidad
        self.country_sites = {
            'ecuador': 'https://ec.computrabajo.com',
            'colombia': 'https://co.computrabajo.com',
            'peru': 'https://pe.computrabajo.com',
            'mexico': 'https://mx.computrabajo.com',
            'argentina': 'https://ar.computrabajo.com',
            'chile': 'https://cl.computrabajo.com',
            'españa': 'https://www.computrabajo.es',
            'españa2': 'https://es.computrabajo.com'
        }
        
        # Estadísticas de operación
        self.stats = {
            'pages_processed': 0,
            'detail_pages_processed': 0,
            'retry_count': 0,
            'errors': {
                'search_pages': 0,
                'detail_pages': 0
            }
        }

    def _get_random_headers(self) -> Dict[str, str]:
        """Obtiene headers aleatorios para parecer más humano"""
        return random.choice(HEADERS_VARIATIONS)

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        if not self.base_url:
            logger.error(f"[{self.source_name}] No hay base_url configurada.")
            return None

        # Limitar y seleccionar keywords más relevantes para reducir restricciones
        # Computrabajo funciona mejor con pocas keywords específicas
        relevant_tech_keywords = ["python", "javascript", "java", "react", "angular", "vue", 
                                  "node", "django", "flask", "data science", "machine learning",
                                  "ai", "desarrollador", "programador", "developer", "fullstack",
                                  "backend", "frontend", "web", "mobile", "data"]
        
        filtered_keywords = []
        # Primero añadir keywords técnicas si están presentes
        for kw in relevant_tech_keywords:
            for user_kw in keywords:
                if kw.lower() in user_kw.lower():
                    filtered_keywords.append(kw)
                    break
                    
        # Asegurar que tengamos algunas keywords, incluso si no son técnicas
        if not filtered_keywords and keywords:
            filtered_keywords = keywords[:MAX_KEYWORDS_IN_URL_COMPUTRABAJO]
            
        # Si no hay ninguna keyword después del filtrado, usar un término genérico de tecnología
        if not filtered_keywords:
            filtered_keywords = ["desarrollador"]
            
        keyword_query = ' '.join(filtered_keywords).strip()
        
        # Determinar valor de ubicación con más opciones
        loc_lower = (location or '').strip().lower()
        is_remote = 'remoto' in loc_lower or 'remote' in loc_lower or 'teletrabajo' in loc_lower
        loc_value: Optional[str] = None

        if is_remote:
            if 'remoto' not in keyword_query.lower():
                keyword_query += ' remoto'
        elif loc_lower == 'quito':
            loc_value = 'Pichincha'
        elif loc_lower == 'guayaquil':
            loc_value = 'Guayas'
        elif loc_lower in ['cuenca', 'azuay']:
            loc_value = 'Azuay'
        elif loc_lower in ['ambato', 'tungurahua']:
            loc_value = 'Tungurahua'
        elif loc_lower in ['loja']:
            loc_value = 'Loja'
        elif location:
            loc_value = location

        # Preparar parámetros
        params: Dict[str, Any] = {}
        if keyword_query:
            params['q'] = quote_plus(keyword_query)
        if loc_value:
            params['p'] = quote_plus(loc_value)
        if page > 1:
            params['pg'] = page

        # Construir la URL con formato más optimizado para Computrabajo
        if 'remoto' in keyword_query.lower():
            base_search_url = f"{self.base_url}/trabajo-remoto/"
        else:
            base_search_url = f"{self.base_url}/ofertas-de-trabajo/"
            
        if params:
            query_string = '&'.join(f"{k}={v}" for k, v in params.items())
            url = f"{base_search_url}?{query_string}"
            logger.debug(f"[{self.source_name}] URL de búsqueda construida: {url}")
            return url
        return base_search_url

    def _parse_relative_date(self, date_str: Optional[str]) -> Optional[str]:
        if not date_str:
            return None
        text = date_str.strip().lower()
        today = datetime.now().date()
        if 'hoy' in text:
            return today.strftime('%Y-%m-%d')
        if 'ayer' in text:
            return (today - timedelta(days=1)).strftime('%Y-%m-%d')
        match = re.search(r'hace\s*(\d+)\s*d[ií]as?', text)
        if match:
            days = int(match.group(1))
            return (today - timedelta(days=days)).strftime('%Y-%m-%d')
        # Intentar formato DD/MM/YYYY
        try:
            dt = datetime.strptime(text, '%d/%m/%Y')
            return dt.strftime('%Y-%m-%d')
        except:
            pass
        # Intentar otro formato común
        try:
            dt = datetime.strptime(text, '%d-%m-%Y')
            return dt.strftime('%Y-%m-%d')
        except:
            pass
        # Más formatos
        try:
            dt = datetime.strptime(text, '%d de %B de %Y')
            return dt.strftime('%Y-%m-%d')
        except:
            pass
        return date_str

    def _process_detail_page(self, url: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa una página de detalle para extraer más información
        
        Args:
            url: URL de la página de detalle
            job_data: Datos básicos recopilados de la página de listado
            
        Returns:
            Diccionario con los datos enriquecidos
        """
        if not url:
            return job_data
            
        try:
            # Añadir espera para parecer humano y evitar bloqueos
            time.sleep(random.uniform(1.0, 2.5))
            
            # Obtener HTML de detalle con reintentos
            detail_html = None
            max_retries = 2
            retry_count = 0
            
            while not detail_html and retry_count < max_retries:
                headers = self._get_random_headers()
                detail_html = self._fetch_html(url, headers=headers)
                
                if not detail_html:
                    retry_count += 1
                    self.stats['retry_count'] += 1
                    logger.warning(f"[{self.source_name}] Reintento {retry_count} para página de detalle: {url}")
                    time.sleep(random.uniform(2.0, 4.0))  # Backoff exponencial
            
            if not detail_html:
                logger.warning(f"[{self.source_name}] No se pudo obtener HTML de detalle después de {max_retries} intentos: {url}")
                self.stats['errors']['detail_pages'] += 1
                return job_data
                
            detail_soup = self._parse_html(detail_html)
            if not detail_soup:
                return job_data
                
            self.stats['detail_pages_processed'] += 1
            
            # Intentar múltiples selectores para ser robusto ante cambios
            
            # 1. Descripción completa
            desc_selectors = [
                'div[itemprop="description"]', 
                'div._description_extend', 
                'div.bWord',
                'div.panel-body',
                'div.js_jobDetailContent',
                'div.p0'
            ]
            
            for selector in desc_selectors:
                desc_el = detail_soup.select_one(selector)
                if desc_el:
                    job_data['descripcion'] = self._safe_get_text(desc_el)
                    break
            
            # 2. Requisitos y detalles adicionales
            req_selectors = [
                'div.box_req', 
                'div.tag-list',
                'div.list_requisitos',
                'ul.p-0',
                '.fs1p0'
            ]
            
            for selector in req_selectors:
                req_el = detail_soup.select(selector)
                if req_el:
                    # Intentar extraer requisitos como lista
                    requirements = []
                    for item in req_el:
                        req_text = self._safe_get_text(item)
                        if req_text:
                            requirements.append(req_text)
                    
                    if requirements:
                        job_data['requisitos'] = requirements
                    break
            
            # 3. Extracción de salario
            if job_data.get('descripcion'):
                for pattern in SALARY_PATTERNS:
                    match = re.search(pattern, job_data['descripcion'], re.IGNORECASE)
                    if match:
                        job_data['salario'] = match.group(1).strip()
                        break
            
            # 4. Modalidad de trabajo (remoto, presencial, híbrido)
            if job_data.get('descripcion'):
                for pattern, value in MODALITY_PATTERNS:
                    if re.search(pattern, job_data['descripcion'], re.IGNORECASE):
                        job_data['modalidad'] = value
                        break
            
            # 5. Fecha de publicación - intentar con más selectores
            date_selectors = [
                'div.fs0.pt10.pb5.fc60.w100',
                'span.dO',
                'p.fs13 span.dO', 
                'p.text-center span',
                '.fs1p0'
            ]
            
            if not job_data.get('fecha_publicacion'):
                for selector in date_selectors:
                    date_el = detail_soup.select_one(selector)
                    if date_el:
                        date_text = self._safe_get_text(date_el)
                        job_data['fecha_publicacion'] = self._parse_relative_date(date_text)
                        break
            
            # 6. Tipo de contrato
            contract_selectors = [
                'p:contains("Tipo de contrato")',
                'div:contains("Tipo de contrato")',
                'p:contains("Jornada")',
                'span:contains("Contrato")'
            ]
            
            for selector in contract_selectors:
                contract_el = detail_soup.select_one(selector)
                if contract_el:
                    contract_text = self._safe_get_text(contract_el)
                    if contract_text and ":" in contract_text:
                        contract_type = contract_text.split(":", 1)[1].strip()
                        job_data['tipo_contrato'] = contract_type
                        break
        
        except Exception as e:
            error_msg = f"Error procesando detalle {url}: {str(e)}"
            logger.error(f"[{self.source_name}] {error_msg}")
            if ERROR_HANDLER_AVAILABLE:
                register_error('detail_processing', self.source_name, error_msg)
            self.stats['errors']['detail_pages'] += 1
        
        return job_data

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_offers: List[Dict[str, Any]] = []
        page = 1
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', '')
        process_detail = search_params.get('process_detail_pages', True)

        # Resetear estadísticas
        self.stats = {
            'pages_processed': 0,
            'detail_pages_processed': 0,
            'retry_count': 0,
            'errors': {
                'search_pages': 0,
                'detail_pages': 0
            }
        }

        while page <= MAX_PAGES_TO_SCRAPE:
            logger.info(f"[{self.source_name}] Procesando página {page}...")
            url = self._build_search_url(keywords, location, page)
            if not url:
                break

            # Añadir headers para parecer más humano
            headers = self._get_random_headers()
            html = self._fetch_html(url, headers=headers)
            
            # Reintento con delay si falla
            if not html:
                retry_delay = random.uniform(2.0, 5.0)
                logger.warning(f"[{self.source_name}] Reintentando página {page} después de {retry_delay:.2f}s")
                time.sleep(retry_delay)
                
                # Usar headers diferentes en el reintento
                headers = self._get_random_headers()
                html = self._fetch_html(url, headers=headers)
            
            if not html:
                logger.warning(f"[{self.source_name}] No HTML en página {page} después del reintento.")
                self.stats['errors']['search_pages'] += 1
                break

            soup = self._parse_html(html)
            if not soup:
                logger.warning(f"[{self.source_name}] No se parseó HTML página {page}.")
                self.stats['errors']['search_pages'] += 1
                break

            # Múltiples selectores para ser robustos ante cambios
            card_selectors = [
                'article.box_offer', 
                'article.iO', 
                'div.iO', 
                'div.bRS',
                'article.js_item', 
                'div.js_offer',
                '.js_list_item',
                'div.iO:not([id])'
            ]
            
            # Intentar diferentes selectores
            cards = []
            for selector in card_selectors:
                cards = soup.select(selector)
                if cards:
                    logger.debug(f"[{self.source_name}] Selector encontrado: {selector}")
                    break
            
            if not cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {page}.")
                break

            self.stats['pages_processed'] += 1
            page_offers_count = 0

            for card in cards:
                oferta = self.get_standard_job_dict()
                
                # Título y URL - múltiples selectores
                title_selectors = [
                    'p.title a', 
                    'a.js-o-link', 
                    'h1.it-title', 
                    'h3.tO a',
                    'h3 a',
                    'a[title]',
                    '.js-o-link',
                    'h2 a'
                ]
                
                for selector in title_selectors:
                    title_el = card.select_one(selector)
                    if title_el:
                        oferta['titulo'] = self._safe_get_text(title_el)
                        href = self._safe_get_attribute(title_el, 'href')
                        oferta['url'] = self._build_url(href)
                        break
                
                # Empresa - múltiples selectores
                company_selectors = [
                    'div.fs16 a', 
                    'span.d-block a', 
                    'p.it-company', 
                    'p.w_100 a',
                    '.it-blank',
                    '.w_100 .fs14',
                    '.fs1p1',
                    'p:nth-child(2) a'
                ]
                
                for selector in company_selectors:
                    comp_el = card.select_one(selector)
                    if comp_el:
                        oferta['empresa'] = self._safe_get_text(comp_el)
                        break

                # Ubicación - múltiples selectores
                location_selectors = [
                    'p span[title]', 
                    'span.location_pub', 
                    'p.w_100 span.pB5',
                    '.item_detail',
                    '.fs13',
                    '.detalle_loc',
                    'p.fs13:nth-child(2)',
                    'span[itemprop="addressLocality"]'
                ]
                
                for selector in location_selectors:
                    loc_el = card.select_one(selector)
                    if loc_el:
                        oferta['ubicacion'] = self._safe_get_text(loc_el)
                        break

                # Fecha - múltiples selectores
                date_selectors = [
                    'p.fs13 span', 
                    'span.date', 
                    'p.fs13.mb10 span',
                    '.dO',
                    'p.fs13 span.dO',
                    '.fs13.color-vac-alt'
                ]
                
                for selector in date_selectors:
                    date_el = card.select_one(selector)
                    if date_el:
                        date_text = self._safe_get_text(date_el)
                        oferta['fecha_publicacion'] = self._parse_relative_date(date_text)
                        break
                
                # Salario - si está visible en la tarjeta
                salary_selectors = [
                    'span.tag.base.salary',
                    'p:contains("Salario:")',
                    'span:contains("$")',
                    '.color_ext',
                    'span.Tag'
                ]
                
                for selector in salary_selectors:
                    salary_el = card.select_one(selector)
                    if salary_el:
                        salary_text = self._safe_get_text(salary_el)
                        if salary_text and ('$' in salary_text or 'salario' in salary_text.lower()):
                            oferta['salario'] = salary_text
                            break

                # Si tenemos título y URL, procesar la oferta
                if oferta['titulo'] and oferta['url']:
                    # Procesar página de detalle si está habilitado
                    if process_detail:
                        oferta = self._process_detail_page(oferta['url'], oferta)
                    
                    # Añadir la oferta incluso si no tiene descripción
                    all_offers.append(oferta)
                    page_offers_count += 1
            
            logger.info(f"[{self.source_name}] Página {page}: {page_offers_count} ofertas procesadas")
                    
            # Retraso entre páginas para parecer más humano
            page_delay = random.uniform(1.5, 3.0)
            logger.debug(f"[{self.source_name}] Esperando {page_delay:.2f}s antes de la siguiente página...")
            time.sleep(page_delay)
            
            # Paginación - múltiples selectores
            pagination_selectors = [
                'a[rel="next"]', 
                'a.paginas:contains("Siguiente")', 
                'li.siguiente a',
                '.pagination a[title="Siguiente"]',
                'a[title="Siguiente"]',
                'a.siguiente',
                'ul.pagination li:last-child a'
            ]
            
            has_next = False
            for selector in pagination_selectors:
                next_link = soup.select_one(selector)
                if next_link:
                    has_next = True
                    break
                    
            if has_next:
                page += 1
            else:
                break

        # Estadísticas finales
        logger.info(f"[{self.source_name}] Total páginas procesadas: {self.stats['pages_processed']}")
        logger.info(f"[{self.source_name}] Total páginas de detalle: {self.stats['detail_pages_processed']}")
        logger.info(f"[{self.source_name}] Total ofertas obtenidas: {len(all_offers)}")
        
        return all_offers

# --- Ejemplo de uso ---
if __name__ == '__main__':
    try:
        from src.utils.logging_config import setup_logging
        setup_logging()
    except ImportError:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
        logging.warning("No se pudo importar setup_logging. Usando config básica.")

    try:
        from src.utils.http_client import HTTPClient
        import pprint
    except ImportError:
        print("ERROR: No se pudo importar HTTPClient o pprint.")
        sys.exit(1)

    http_client = HTTPClient()
    config = {'base_url': 'https://ec.computrabajo.com'}
    scraper = ComputrabajoScraperImproved(http_client=http_client, config=config)
    params = {'keywords': ['programador', 'python'], 'location': 'Quito', 'process_detail_pages': True}

    print(f"Iniciando prueba mejorada: {params}")
    results = scraper.fetch_jobs(params)
    print(f"Ofertas encontradas: {len(results)}")
    if results:
        pprint.pprint(results[0])
    http_client.close()
