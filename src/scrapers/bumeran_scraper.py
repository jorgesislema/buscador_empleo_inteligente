# -*- coding: utf-8 -*-
# /src/scrapers/bumeran_scraper.py

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re
from urllib.parse import quote, urljoin

from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE_BUMERAN = 10

class BumeranScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="bumeran", http_client=http_client, config=config)
        if not self.base_url:
            self.base_url = "https://www.bumeran.com.ec/"

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        keyword_slug = '-'.join(quote(k.strip()) for k in keywords if k.strip()).lower()
        location_slug = ""
        loc_lower = location.lower().strip() if location else ""

        if any(term in loc_lower for term in ['remote', 'remoto', 'teletrabajo']):
            if 'remoto' not in keyword_slug:
                keyword_slug = f"{keyword_slug}-remoto" if keyword_slug else "remoto"
        elif loc_lower:
            location_slug = quote(loc_lower.replace(" ", "-"))

        path = "/empleos"
        if keyword_slug:
            path += f"-busqueda-{keyword_slug}"
        if location_slug:
            path += f"-localidad-{location_slug}"
        if page > 1:
            path += f"-pagina-{page}"
        path += ".html"

        full_url = f"{self.base_url.rstrip('/')}{path}"
        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', 'Quito')

        while current_page <= MAX_PAGES_TO_SCRAPE_BUMERAN:
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
                logger.warning(f"[{self.source_name}] No se parseó HTML de página {current_page}.")
                break

            job_cards = soup.select('div.aviso-container, div#listado-avisos > div')
            if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}. Fin.")
                break

            logger.info(f"[{self.source_name}] {len(job_cards)} ofertas encontradas en página {current_page}.")

            for card in job_cards:
                oferta = self.get_standard_job_dict()

                title_link_element = card.select_one('a.titulo-aviso, h2.job-title a')
                oferta['titulo'] = self._safe_get_text(title_link_element)
                detail_url_relative = self._safe_get_attribute(title_link_element, 'href')
                oferta['url'] = self._build_url(detail_url_relative)

                company_element = card.select_one('a.empresa-nombre, h3.job-company')
                oferta['empresa'] = self._safe_get_text(company_element)

                location_element = card.select_one('span.detalle-aviso-location, div.job-location')
                oferta['ubicacion'] = self._safe_get_text(location_element)

                date_element = card.select_one('h4.fecha, span.job-date')
                date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text)

                oferta['descripcion'] = None
                if oferta['url']:
                    detail_html = self._fetch_html(oferta['url'])
                    detail_soup = self._parse_html(detail_html)
                    if detail_soup:
                        desc_container = detail_soup.select_one('div.aviso_description, div.job-description-detail')
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

            next_page_link = soup.select_one('a.nav-pag-arrow-right:not(.disabled), li.next:not(.disabled) a')
            if next_page_link:
                current_page += 1
            else:
                logger.info(f"[{self.source_name}] No se encontró enlace 'Siguiente'. Fin.")
                break

        logger.info(f"[{self.source_name}] Búsqueda finalizada. {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers


if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()

    bumeran_config = {
        'enabled': True,
        'base_url': 'https://www.bumeran.com.ec/'
    }

    scraper = BumeranScraper(http_client=http_client, config=bumeran_config)
    search_params = {
        'keywords': ['supervisor'],
        'location': 'Quito'
    }

    ofertas = scraper.fetch_jobs(search_params)
    print(f"\nSe encontraron {len(ofertas)} ofertas.")
    if ofertas:
        pprint.pprint(ofertas[0])

    http_client.close()
