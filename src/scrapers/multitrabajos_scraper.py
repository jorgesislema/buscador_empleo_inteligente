# -*- coding: utf-8 -*-
# /src/scrapers/multitrabajos_scraper.py

"""
Scraper específico para el portal Multitrabajos (Ecuador).

Hereda de BaseScraper y define la lógica para extraer ofertas
de multitrabajos.com.

Compañero, ¡ya sabes el trato! Revisa y ajusta los selectores CSS
y la lógica de construcción de URLs según la estructura actual de la web.
¡A ponerse el sombrero de detective HTML! 🕵️‍♀️
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re
from urllib.parse import quote
import random

from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE_MULTITRABAJOS = 10

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

class MultitrabajosScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="multitrabajos", http_client=http_client, config=config)
        if not self.base_url or 'multitrabajos.com' not in self.base_url:
            self.base_url = "https://www.multitrabajos.com"
            logger.warning(f"[{self.source_name}] Usando URL base por defecto: {self.base_url}")

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        keyword_slug = '-'.join(k.strip() for k in keywords if k.strip()).lower()
        keyword_slug = quote(keyword_slug)

        location_slug = ""
        loc_lower = location.lower().strip() if location else ""

        if any(term in loc_lower for term in ['remote', 'remoto', 'teletrabajo']):
            if 'remoto' not in keyword_slug:
                keyword_slug = f"{keyword_slug}-remoto" if keyword_slug else "remoto"
        else:
            location_slug = quote(loc_lower.replace(" ", "-"))

        if keyword_slug and location_slug:
            path = f"/empleos-busqueda-{keyword_slug}-en-{location_slug}.html"
        elif keyword_slug:
            path = f"/empleos-busqueda-{keyword_slug}.html"
        elif location_slug:
            path = f"/empleos-en-{location_slug}.html"
        else:
            path = "/empleos.html"

        page_param = f"?page={page}" if page > 1 else ""
        full_url = f"{self.base_url.rstrip('/')}{path}{page_param}"
        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url

    def _parse_relative_date(self, date_str: Optional[str]) -> Optional[str]:
        if not date_str:
            return None
        date_str_lower = date_str.lower().strip()
        today = datetime.now().date()

        if 'publicado hoy' in date_str_lower:
            return today.strftime('%Y-%m-%d')
        elif 'publicado ayer' in date_str_lower:
            return (today - timedelta(days=1)).strftime('%Y-%m-%d')
        elif 'publicado hace' in date_str_lower:
            match = re.search(r'hace\s+(\d+)\s+días?', date_str_lower)
            if match:
                try:
                    days_ago = int(match.group(1))
                    return (today - timedelta(days=days_ago)).strftime('%Y-%m-%d')
                except ValueError:
                    logger.warning(f"[{self.source_name}] No se pudo convertir días en: '{date_str}'")
        return date_str

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

        while current_page <= MAX_PAGES_TO_SCRAPE_MULTITRABAJOS:
            logger.info(f"[{self.source_name}] Procesando página {current_page}...")
            current_url = self._build_search_url(keywords, location, current_page)
            if not current_url:
                logger.error(f"[{self.source_name}] URL inválida para página {current_page}. Abortando.")
                break

            html_content = self._fetch_html_with_retry(current_url)
            if not html_content:
                logger.warning(f"[{self.source_name}] No se obtuvo HTML de página {current_page}. Terminando.")
                break

            soup = self._parse_html(html_content)
            if not soup:
                logger.warning(f"[{self.source_name}] No se parseó HTML de página {current_page}. Terminando.")
                break

            job_cards = soup.select('div.aviso-container, article[data-id-aviso], div.job-card, div.job-listing')
            if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}. Fin.")
                break

            for card in job_cards:
                oferta = self.get_standard_job_dict()
                title_link_element = card.select_one('h2 a, a.titulo-aviso, a.job-title')
                oferta['titulo'] = self._safe_get_text(title_link_element)
                detail_url_relative = self._safe_get_attribute(title_link_element, 'href')
                oferta['url'] = self._build_url(detail_url_relative)

                company_element = card.select_one('h3[data-company-name], span.nombre-empresa, div.company, span.company')
                oferta['empresa'] = self._safe_get_text(company_element)
                if not oferta['empresa'] and company_element:
                    oferta['empresa'] = company_element.get('data-company-name')

                location_element = card.select_one('span.location-text, div.ubicacion span, span.location, div.location')
                oferta['ubicacion'] = self._safe_get_text(location_element)

                date_element = card.select_one('h4.fecha, span.fecha-publicacion, span.date, time')
                date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text)

                oferta['descripcion'] = None
                if oferta['url']:
                    detail_html = self._fetch_html_with_retry(oferta['url'])
                    detail_soup = self._parse_html(detail_html)
                    if detail_soup:
                        desc_container = detail_soup.select_one('div.aviso_description, section.detalle-aviso, div.job-description, div.description')
                        if desc_container:
                            paragraphs = desc_container.find_all('p')
                            if paragraphs:
                                oferta['descripcion'] = "\n".join([
                                    self._safe_get_text(p) for p in paragraphs if self._safe_get_text(p)
                                ])
                            else:
                                oferta['descripcion'] = self._safe_get_text(desc_container)

                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)

            next_page_link_element = soup.select_one('a.nav-pag-arrow-right, li.next a, a.next, a[rel="next"]')
            if next_page_link_element:
                next_page_href = self._safe_get_attribute(next_page_link_element, 'href')
                if next_page_href and next_page_href != '#':
                    current_url = self._build_url(next_page_href)
                    current_page += 1
                    continue
                else:
                    break
            else:
                break

        logger.info(f"[{self.source_name}] Búsqueda finalizada. {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers
