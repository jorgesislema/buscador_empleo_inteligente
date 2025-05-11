# -*- coding: utf-8 -*-
# /src/scrapers/remoterocketship_scraper.py

"""
Scraper para RemoteRocketship.com: extrae ofertas de trabajo remoto.
Ajustar selectores si el sitio cambia estructura.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re
from urllib.parse import quote_plus, urljoin

from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE_ROCKETSHIP = 5

class RemoteRocketshipScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="remoterocketship", http_client=http_client, config=config)
        if not self.base_url:
            self.base_url = "https://remoterocketship.com/"
            logger.info(f"[{self.source_name}] Usando base_url por defecto: {self.base_url}")

    def _build_search_url(self, keywords: List[str], page: int = 1) -> Optional[str]:
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin base_url.")
            return None

        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''
        search_url = f"{self.base_url.rstrip('/')}/"
        if keyword_query:
            search_url += f"?search={keyword_query}"
        if page > 1:
            search_url += f"&page={page}" if '?' in search_url else f"?page={page}"
        logger.debug(f"[{self.source_name}] URL construida: {search_url}")
        return search_url

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])

        while current_page <= MAX_PAGES_TO_SCRAPE_ROCKETSHIP:
            logger.info(f"[{self.source_name}] Procesando página {current_page}...")
            current_url = self._build_search_url(keywords, current_page)
            if not current_url:
                break

            html_content = self._fetch_html(current_url)
            if not html_content:
                break

            soup = self._parse_html(html_content)
            if not soup:
                break

            job_cards = soup.select('div.job-listing-item, li.job-item')
            if not job_cards:
                logger.info(f"[{self.source_name}] No hay más ofertas.")
                break

            for card in job_cards:
                oferta = self.get_standard_job_dict()
                title_link_element = card.select_one('h2 a, a.job-title-link')
                oferta['titulo'] = self._safe_get_text(title_link_element)
                oferta['url'] = self._safe_get_attribute(title_link_element, 'href')
                if oferta['url'] and oferta['url'].startswith('/'):
                    oferta['url'] = urljoin(self.base_url, oferta['url'])

                company_element = card.select_one('span.company-name, div.company-info a')
                oferta['empresa'] = self._safe_get_text(company_element)

                location_element = card.select_one('span.location-restriction, div.job-location')
                oferta['ubicacion'] = self._safe_get_text(location_element)

                date_element = card.select_one('span.date-posted, time.datetime-posted')
                date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text)

                tags_elements = card.select('span.tag, div.tags a')
                tags = [self._safe_get_text(tag) for tag in tags_elements if self._safe_get_text(tag)]
                oferta['descripcion'] = f"Tags: {', '.join(tags)}" if tags else None

                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)
                else:
                    logger.warning(f"[{self.source_name}] Oferta omitida por faltar título o URL.")

            next_page_link_element = soup.select_one('a.next-page-link, li.pagination-next a')
            if next_page_link_element:
                next_page_href = self._safe_get_attribute(next_page_link_element, 'href')
                if next_page_href and next_page_href != '#':
                    current_page += 1
                else:
                    break
            else:
                break

        logger.info(f"[{self.source_name}] Búsqueda finalizada. Total: {len(all_job_offers)} ofertas.")
        return all_job_offers

if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()

    config = { 'enabled': True, 'base_url': 'https://remoterocketship.com/' }
    scraper = RemoteRocketshipScraper(http_client=http_client, config=config)
    search_params = { 'keywords': ['python', 'developer'], 'location': 'Remote' }

    print("\n--- Iniciando prueba de RemoteRocketshipScraper ---")
    try:
        ofertas = scraper.fetch_jobs(search_params)
        print(f"\n--- {len(ofertas)} ofertas encontradas ---")
        if ofertas:
            pprint.pprint(ofertas[0])
    finally:
        http_client.close()
