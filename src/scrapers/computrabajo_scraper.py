# -*- coding: utf-8 -*-
# /src/scrapers/computrabajo_scraper.py

"""
Scraper para Computrabajo Ecuador (ec.computrabajo.com).
Verifica correctamente los selectores CSS y parámetros de URL usando DevTools.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus, urljoin
import sys

# Importaciones robustas
try:
    from src.scrapers.base_scraper import BaseScraper
    from src.utils.http_client import HTTPClient
    from src.utils import config_loader
except ImportError:
    logging.basicConfig(level=logging.WARNING)
    logging.warning("Fallo al importar módulos de src en computrabajo_scraper. Usando stubs.")

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

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE = 10
MAX_KEYWORDS_IN_URL_COMPUTRABAJO = 5

class ComputrabajoScraper(BaseScraper):
    """Scraper para Computrabajo Ecuador"""

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="computrabajo", http_client=http_client, config=config or {})
        # Configuración de base_url con fallback
        self.base_url = (self.base_url or config.get('base_url', 'https://ec.computrabajo.com')).rstrip('/')
        logger.debug(f"[{self.source_name}] Base URL: {self.base_url}")

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        if not self.base_url:
            logger.error(f"[{self.source_name}] No hay base_url configurada.")
            return None

        # Limitar y seleccionar keywords más relevantes para reducir restricciones
        # Computrabajo funciona mejor con pocas keywords específicas
        relevant_tech_keywords = ["python", "javascript", "java", "react", "angular", "vue", 
                                 "node", "django", "flask", "data science", "machine learning",
                                 "ai", "desarrollador", "programador", "developer"]
        
        filtered_keywords = []
        # Primero añadir keywords técnicas si están presentes
        for kw in relevant_tech_keywords:
            for user_kw in keywords:
                if kw.lower() in user_kw.lower():
                    filtered_keywords.append(kw)
                    break
                    
        # Asegurar que tengamos algunas keywords, incluso si no son técnicas
        if not filtered_keywords and keywords:
            filtered_keywords = keywords[:3]  # Solo usar las primeras 3 keywords
            
        # Si no hay ninguna keyword después del filtrado, usar un término genérico de tecnología
        if not filtered_keywords:
            filtered_keywords = ["desarrollador"]
            
        keyword_query = ' '.join(filtered_keywords).strip()
        
        # Determinar valor de ubicación
        loc_lower = (location or '').strip().lower()
        is_remote = 'remoto' in loc_lower or 'remote' in loc_lower
        loc_value: Optional[str] = None

        if is_remote:
            if 'remoto' not in keyword_query.lower():
                keyword_query += ' remoto'
        elif loc_lower == 'quito':
            loc_value = 'Pichincha'
        elif loc_lower == 'guayaquil':
            loc_value = 'Guayas'
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
        return date_str

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_offers: List[Dict[str, Any]] = []
        page = 1
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', '')

        while page <= MAX_PAGES_TO_SCRAPE:
            logger.info(f"[{self.source_name}] Procesando página {page}...")
            url = self._build_search_url(keywords, location, page)
            if not url:
                break

            html = self._fetch_html(url)
            if not html:
                logger.warning(f"[{self.source_name}] No HTML en página {page}.")
                break

            soup = self._parse_html(html)
            if not soup:
                logger.warning(f"[{self.source_name}] No se parseó HTML página {page}.")
                break

            # Selectores actualizados para el sitio actual de Computrabajo
            # Probamos varios selectores para ser más robustos ante cambios
            cards = soup.select('article.box_offer, article.iO, div.iO, div.bRS')
            if not cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {page}.")
                break

            for card in cards:
                oferta = self.get_standard_job_dict()
                # Título y URL - selectores actualizados
                title_el = card.select_one('p.title a, a.js-o-link, h1.it-title, h3.tO a')
                oferta['titulo'] = self._safe_get_text(title_el)
                href = self._safe_get_attribute(title_el, 'href')
                oferta['url'] = self._build_url(href)

                # Empresa - selectores actualizados
                comp_el = card.select_one('div.fs16 a, span.d-block a, p.it-company, p.w_100 a')
                oferta['empresa'] = self._safe_get_text(comp_el)

                # Ubicación - selectores actualizados
                loc_el = card.select_one('p span[title], span.location_pub, p.w_100 span.pB5')
                oferta['ubicacion'] = self._safe_get_text(loc_el)

                # Fecha - selectores actualizados 
                date_el = card.select_one('p.fs13 span, span.date, p.fs13.mb10 span')
                date_text = self._safe_get_text(date_el)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text)

                # Si no pudimos obtener la descripción en la lista, intentamos obtenerla de la página de detalle
                if oferta['titulo'] and oferta['url']:
                    try:
                        # A veces extraer la descripción puede fallar, pero queremos mantener el resto de la oferta
                        detail_html = self._fetch_html(oferta['url'])
                        detail_soup = self._parse_html(detail_html) if detail_html else None
                        if detail_soup:
                            # Selectores actualizados para la descripción
                            desc_el = detail_soup.select_one('div[itemprop="description"], div._description_extend, div.panel-body, div.bWord')
                            oferta['descripcion'] = self._safe_get_text(desc_el)
                    except Exception as e:
                        logger.warning(f"[{self.source_name}] Error obteniendo descripción para {oferta['url']}: {e}")
                        oferta['descripcion'] = None
                    
                    # Añadir la oferta incluso si no tiene descripción
                    all_offers.append(oferta)
                    
            # Paginación - selectores actualizados
            next_link = soup.select_one('a[rel="next"], a.paginas:contains("Siguiente"), li.siguiente a')
            if next_link:
                page += 1
            else:
                break

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
    scraper = ComputrabajoScraper(http_client=http_client, config=config)
    params = {'keywords': ['programador', 'python'], 'location': 'Quito'}

    print(f"Iniciando prueba: {params}")
    results = scraper.fetch_jobs(params)
    print(f"Ofertas encontradas: {len(results)}")
    if results:
        pprint.pprint(results[0])
    http_client.close()
