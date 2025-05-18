# -*- coding: utf-8 -*-
# /src/scrapers/portalempleoec_scraper.py

"""
Scraper para el portal Encuentra Empleo del Gobierno de Ecuador.
Hereda de BaseScraper y adapta su estructura a los patrones del sitio.
"""

import logging
import random
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import quote_plus, urljoin

from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE_PORTALEC = 10

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

class PortalempleoecScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="portalempleoec", http_client=http_client, config=config)
        self.base_url = self.base_url or "https://encuentraempleo.trabajo.gob.ec/"
        logger.info(f"[{self.source_name}] Usando URL base: {self.base_url}")

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''
        location_query = quote_plus(location) if location else ''
        params = {}

        if keyword_query:
            params['keywords'] = keyword_query
        if location_query:
            if location.lower() == 'quito':
                params['provincia'] = 'Pichincha'
            elif 'remoto' in location.lower():
                params['modalidad'] = 'Teletrabajo'
            else:
                params['provincia'] = location
        if page > 1:
            params['page'] = page

        search_path = "/empleo/busqueda.do"
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{self.base_url.rstrip('/')}/{search_path.lstrip('/')}"
        if query_string:
            full_url += f"?{query_string}"
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
        logger.info(f"[{self.source_name}] Iniciando scraping con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', 'Quito')

        while current_page <= MAX_PAGES_TO_SCRAPE_PORTALEC:
            current_url = self._build_search_url(keywords, location, current_page)
            html_content = self._fetch_html_with_retry(current_url)
            if not html_content:
                break

            soup = self._parse_html(html_content)
            if not soup:
                break

            job_cards = soup.select('div.row.result-container, tr.oferta-row, div.job-card, div.job')
            if not job_cards:
                break

            for card in job_cards:
                oferta = self.get_standard_job_dict()

                title_link_element = card.select_one('a.titulo-oferta, td.job-title a, a.job-title')
                oferta['titulo'] = self._safe_get_text(title_link_element)
                href = self._safe_get_attribute(title_link_element, 'href')
                oferta['url'] = self._build_url(href)

                empresa = card.select_one('span.institucion, td.company-name, span.company, div.company')
                oferta['empresa'] = self._safe_get_text(empresa)

                ubicacion = card.select_one('span.ubicacion, td.location, span.location, div.location')
                oferta['ubicacion'] = self._safe_get_text(ubicacion)

                fecha = card.select_one('span.fecha-publicacion, td.date, span.date, time')
                oferta['fecha_publicacion'] = self._parse_relative_date(self._safe_get_text(fecha))

                if oferta['url']:
                    detalle_html = self._fetch_html_with_retry(oferta['url'])
                    detalle_soup = self._parse_html(detalle_html)
                    if detalle_soup:
                        desc = detalle_soup.select_one('div#descripcion, div.detalle-descripcion, div.description, div.job-desc')
                        oferta['descripcion'] = self._safe_get_text(desc)

                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)

            next_link = soup.select_one('a.siguiente, li.next a, a.next, a[rel="next"]')
            href = self._safe_get_attribute(next_link, 'href')
            if not href or href == '#':
                break
            current_page += 1

        logger.info(f"[{self.source_name}] {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers
