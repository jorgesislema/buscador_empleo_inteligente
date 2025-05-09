# -*- coding: utf-8 -*-
# /src/scrapers/tecnoempleo_scraper.py

"""
Scraper específico para el portal Tecnoempleo (España).

Hereda de BaseScraper y se encarga de la lógica para extraer
ofertas de empleo del sector tecnológico en tecnoempleo.com.

¡Compañero! Este es otro desafío de scraping. Revisa con cuidado
la web de Tecnoempleo y ajusta los selectores y la lógica de URL.
¡La precisión es clave!
"""

import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus

from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE_TECNOEMPLEO = 10

class TecnoempleoScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="tecnoempleo", http_client=http_client, config=config)
        if not self.base_url:
            self.base_url = "https://www.tecnoempleo.com/"
            logger.warning(f"[{self.source_name}] 'base_url' no encontrada. Usando default: {self.base_url}")

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        keyword_query = '/'.join(quote_plus(k.strip()) for k in keywords if k.strip()).lower()

        params = {}
        loc_lower = location.lower().strip() if location else ""

        if any(term in loc_lower for term in ['remote', 'remoto', 'teletrabajo', 'españa']):
            params['teletrabajo'] = '1'
            params['prov'] = quote_plus(location)

        if keyword_query:
            params['tec'] = keyword_query
        if page > 1:
            params['p'] = page

        search_path = "/ofertas-trabajo/"
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()]) if params else ''

        full_url = f"{self.base_url.rstrip('/')}{search_path}"
        if query_string:
            full_url += f"?{query_string}"

        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', 'Remote Spain')

        while current_page <= MAX_PAGES_TO_SCRAPE_TECNOEMPLEO:
            logger.info(f"[{self.source_name}] Procesando página {current_page}...")

            current_url = self._build_search_url(keywords, location, current_page)
            if not current_url:
                logger.error(f"[{self.source_name}] URL inválida para página {current_page}. Abortando.")
                break

            html_content = self._fetch_html(current_url)
            if not html_content:
                logger.warning(f"[{self.source_name}] No se obtuvo HTML de página {current_page}. Terminando.")
                break

            soup = self._parse_html(html_content)
            if not soup:
                logger.warning(f"[{self.source_name}] No se parseó HTML de página {current_page}. Terminando.")
                break

            job_cards = soup.select('article.p-2.border-bottom.py-3')
            if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}. Fin.")
                break

            logger.info(f"[{self.source_name}] {len(job_cards)} ofertas encontradas en página {current_page}.")

            for card in job_cards:
                oferta = self.get_standard_job_dict()

                title_link_element = card.select_one('h2 > a.text-decoration-none')
                oferta['titulo'] = self._safe_get_text(title_link_element)
                detail_url_relative = self._safe_get_attribute(title_link_element, 'href')
                oferta['url'] = self._build_url(detail_url_relative)

                company_element = card.select_one('a[href*="/empresa/"] > strong')
                oferta['empresa'] = self._safe_get_text(company_element)

                location_element = card.select_one('ul.list-inline li a[href*="/provincia/"]')
                if not location_element:
                    location_element = card.select_one('ul.list-inline li:-soup-contains("Teletrabajo")')
                oferta['ubicacion'] = self._safe_get_text(location_element)

                date_element = card.select_one('span.text-muted.fs--15')
                date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text)

                oferta['descripcion'] = None
                if oferta['url']:
                    logger.debug(f"[{self.source_name}] Visitando detalle: {oferta['url']}")
                    detail_html = self._fetch_html(oferta['url'])
                    detail_soup = self._parse_html(detail_html)
                    if detail_soup:
                        desc_container = detail_soup.select_one('section#section-description, div.offer-description')
                        if desc_container:
                            oferta['descripcion'] = self._safe_get_text(desc_container)
                        else:
                            logger.warning(f"[{self.source_name}] No se encontró descripción en: {oferta['url']}")
                    else:
                        logger.warning(f"[{self.source_name}] No se pudo parsear detalle para: {oferta['url']}")
                else:
                    logger.warning(f"[{self.source_name}] No URL de detalle para: {oferta['titulo']}")

                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)
                else:
                    logger.warning(f"[{self.source_name}] Oferta omitida por faltar título o URL.")

            next_page_link_element = soup.select_one('a.page-link[rel="next"]')
            if next_page_link_element:
                next_page_href = self._safe_get_attribute(next_page_link_element, 'href')
                if next_page_href and next_page_href != '#':
                    current_url = self._build_url(next_page_href)
                    if not current_url:
                        logger.error(f"[{self.source_name}] No se pudo construir URL siguiente desde href: {next_page_href}")
                        break
                    current_page += 1
                    logger.debug(f"[{self.source_name}] Pasando a página siguiente: {current_url}")
                else:
                    logger.info(f"[{self.source_name}] Enlace 'Siguiente' no válido. Fin.")
                    break
            else:
                logger.info(f"[{self.source_name}] No se encontró enlace 'Siguiente'. Fin.")
                break

        logger.info(f"[{self.source_name}] Búsqueda finalizada. {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers
