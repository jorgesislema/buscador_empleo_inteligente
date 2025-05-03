# -*- coding: utf-8 -*-
# /src/scrapers/jooble_scraper.py

"""
Scraper para el portal Jooble (ej. ec.jooble.org).
Advertencia: Jooble ofrece una API oficial. Este scraper accede a su web,
lo cual puede ser menos fiable o violar sus términos. Usa bajo tu criterio.
"""

import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus, urljoin
from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE_JOOBLE = 5

class JoobleScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="jooble", http_client=http_client, config=config)
        if not self.base_url:
            self.base_url = "https://ec.jooble.org"
        logger.warning(f"[{self.source_name}] Scraper web activado. Considera usar su API oficial.")

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''
        location_slug = quote_plus(location.lower().replace(" ", "-")) if location else ''
        path = f"/jobs-{keyword_query}/{location_slug}" if keyword_query else f"/jobs/{location_slug}"
        page_param = f"?p={page}" if page > 1 else ""
        search_url = f"{self.base_url.rstrip('/')}{path}{page_param}"

        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {search_url}")
        return search_url

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', 'Quito')

        while current_page <= MAX_PAGES_TO_SCRAPE_JOOBLE:
            current_url = self._build_search_url(keywords, location, current_page)
            if not current_url:
                break

            html_content = self._fetch_html(current_url)
            if not html_content:
                break

            soup = self._parse_html(html_content)
            if not soup:
                break

            job_cards = soup.select('article[data-test-id="vacancy-snippet"]')
            if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}.")
                break

            for card in job_cards:
                oferta = self.get_standard_job_dict()
                title_element = card.select_one('h2 a, div[data-test-id="vacancy-title"] a')
                oferta['titulo'] = self._safe_get_text(title_element)
                oferta['url'] = self._safe_get_attribute(title_element, 'href')
                if oferta['url'] and not oferta['url'].startswith('http'):
                    oferta['url'] = urljoin(self.base_url, oferta['url'])

                company_element = card.select_one('span[data-test-id="company-name"], div.company-name')
                oferta['empresa'] = self._safe_get_text(company_element)

                location_element = card.select_one('div[data-test-id="location"] span, div.location')
                oferta['ubicacion'] = self._safe_get_text(location_element)

                date_element = card.select_one('div.date-text, span.date')
                date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text)

                snippet_element = card.select_one('div.description-snippet, span.job-description')
                oferta['descripcion'] = self._safe_get_text(snippet_element)

                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)
                else:
                    logger.warning(f"[{self.source_name}] Oferta omitida por faltar título o URL.")

            next_page_element = soup.select_one('a[data-test-id="pagination-item-next"], a.pagination-next')
            if next_page_element:
                next_href = self._safe_get_attribute(next_page_element, 'href')
                if next_href and next_href != '#':
                    current_url = urljoin(self.base_url, next_href)
                    current_page += 1
                    continue
            break

        logger.info(f"[{self.source_name}] Búsqueda finalizada. {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers
