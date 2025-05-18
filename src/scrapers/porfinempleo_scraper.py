# -*- coding: utf-8 -*-
# /src/scrapers/porfinempleo_scraper.py

"""
Scraper para PorfinEmpleo.com (Ecuador).
"""

import logging
import random
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus, urljoin
from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE_PORFINEMPLEO = 10

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

class PorfinempleoScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="porfinempleo", http_client=http_client, config=config)
        if not self.base_url:
            self.base_url = "https://www.porfinempleo.com/"

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''
        location_query = quote_plus(location) if location else ''

        search_path = "/ofertas-trabajo/"
        params = {}
        if keyword_query:
            params['q'] = keyword_query
        if location_query:
            params['location'] = location_query
        if page > 1:
            params['page'] = page

        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{self.base_url.rstrip('/')}{search_path}"
        if query_string:
            full_url += f"?{query_string}"

        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url

    def _fetch_html_with_retry(self, url, max_retries=3):
        for attempt in range(max_retries):
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            html = self._fetch_html(url, headers=headers)
            if html:
                return html
            logger.warning(f"[{self.source_name}] Reintento {attempt+1} fallido para {url}")
        logger.error(f"[{self.source_name}] Fallaron todos los reintentos para {url}")
        return None

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', 'Quito')

        while current_page <= MAX_PAGES_TO_SCRAPE_PORFINEMPLEO:
            logger.info(f"[{self.source_name}] Procesando página {current_page}...")
            current_url = self._build_search_url(keywords, location, current_page)
            if not current_url:
                break

            html_content = self._fetch_html_with_retry(current_url)
            if not html_content:
                break

            soup = self._parse_html(html_content)
            if not soup:
                break

            job_cards = soup.select('div.job-listing, article.offer-card, div.job-card, div.job')
            if not job_cards:
                break

            logger.info(f"[{self.source_name}] {len(job_cards)} ofertas encontradas en página {current_page}.")

            for card in job_cards:
                oferta = self.get_standard_job_dict()
                title_link = card.select_one('h2.job-title a, a.offer-link, a.job-title')
                oferta['titulo'] = self._safe_get_text(title_link)
                href = self._safe_get_attribute(title_link, 'href')
                oferta['url'] = self._build_url(href)

                company_element = card.select_one('span.company-name, div.company a, span.company, div.company')
                oferta['empresa'] = self._safe_get_text(company_element)

                location_element = card.select_one('span.location, div.job-location, span.location-text, div.location')
                oferta['ubicacion'] = self._safe_get_text(location_element)

                date_element = card.select_one('span.date, time.post-date, span.date-published, time')
                date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text)

                oferta['descripcion'] = None
                if oferta['url']:
                    detail_html = self._fetch_html_with_retry(oferta['url'])
                    detail_soup = self._parse_html(detail_html)
                    if detail_soup:
                        desc_container = detail_soup.select_one('div.job-description, section.offer-details, div.description, div.job-desc')
                        oferta['descripcion'] = self._safe_get_text(desc_container)

                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)

            next_page_element = soup.select_one('a.next-page, li.pagination-next a, a.next, a[rel="next"]')
            if next_page_element:
                href = self._safe_get_attribute(next_page_element, 'href')
                if href and href != '#':
                    current_page += 1
                    continue
            break

        logger.info(f"[{self.source_name}] Búsqueda finalizada. {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers

if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()

    config = {
        'enabled': True,
        'base_url': 'https://www.porfinempleo.com/'
    }
    scraper = PorfinempleoScraper(http_client=http_client, config=config)

    search_params = {
        'keywords': ['ingeniero', 'sistemas'],
        'location': 'Quito'
    }

    print("\n--- Iniciando prueba de PorfinempleoScraper ---")
    try:
        ofertas = scraper.fetch_jobs(search_params)
        print(f"\n--- Prueba finalizada ---\nSe encontraron {len(ofertas)} ofertas.")
        if ofertas:
            pprint.pprint(ofertas[0])
    except Exception as e:
        logger.exception("Error en prueba de PorfinempleoScraper")
    finally:
        http_client.close()
