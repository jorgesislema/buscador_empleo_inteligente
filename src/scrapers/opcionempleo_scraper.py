# -*- coding: utf-8 -*-
# /src/scrapers/opcionempleo_scraper.py

"""
Scraper específico para el agregador de empleos Opcionempleo.

Hereda de BaseScraper y adapta la lógica para extraer ofertas
de la web de Opcionempleo (ej: opcionempleo.ec para Ecuador).

Ojo, compañero: Como Opcionempleo es un agregador, es probable que
solo obtengamos datos básicos y un enlace a la fuente original.
¡Y no olvides verificar los selectores CSS en su web!
"""

import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus, urljoin

from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE_OPCIONEMPLEO = 10

class OpcionempleoScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="opcionempleo", http_client=http_client, config=config)
        if not self.base_url:
            self.base_url = "https://www.opcionempleo.ec/"

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''
        location_query = quote_plus(location) if location else ''

        params = {}
        if keyword_query:
            params['s'] = keyword_query
        if location_query:
            params['l'] = location_query
        if page > 1:
            params['p'] = page

        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{self.base_url.rstrip('/')}/busqueda/empleos"
        if query_string:
            full_url += f"?{query_string}"

        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Iniciando búsqueda web con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', 'Quito')

        while current_page <= MAX_PAGES_TO_SCRAPE_OPCIONEMPLEO:
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

            job_cards = soup.select('article.job, div.job-listing')
            if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}. Fin.")
                break

            logger.info(f"[{self.source_name}] {len(job_cards)} ofertas encontradas en página {current_page}.")

            for card in job_cards:
                oferta = self.get_standard_job_dict()

                title_link_element = card.select_one('header a, h2 a.job_link')
                oferta['titulo'] = self._safe_get_text(title_link_element)
                oferta['url'] = self._safe_get_attribute(title_link_element, 'href')
                if oferta['url'] and not oferta['url'].startswith('http'):
                    oferta['url'] = urljoin(self.base_url, oferta['url'])

                company_element = card.select_one('p.company, span.job-company')
                oferta['empresa'] = self._safe_get_text(company_element)

                location_element = card.select_one('p.location, span.job-location')
                oferta['ubicacion'] = self._safe_get_text(location_element)

                date_element = card.select_one('p.date, span.job-date')
                date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text)

                snippet_element = card.select_one('div.desc, p.job-snippet')
                oferta['descripcion'] = self._safe_get_text(snippet_element)

                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)
                else:
                    logger.warning(f"[{self.source_name}] Oferta omitida por faltar título o URL.")

            next_page_link_element = soup.select_one('a.next, li.next a')
            if next_page_link_element:
                next_page_href = self._safe_get_attribute(next_page_link_element, 'href')
                if next_page_href and next_page_href != '#':
                    try:
                        if next_page_href.startswith('http'):
                            current_url = next_page_href
                        elif next_page_href.startswith('/'):
                            current_url = self._build_url(next_page_href)
                        else:
                            current_url = urljoin(current_url, next_page_href)
                        current_page += 1
                        logger.debug(f"[{self.source_name}] Pasando a página siguiente: {current_url}")
                    except Exception:
                        logger.error(f"[{self.source_name}] No se pudo construir URL de paginación desde '{current_url}' y '{next_page_href}'")
                        break
                else:
                    logger.info(f"[{self.source_name}] Enlace 'Siguiente' no válido. Fin.")
                    break
            else:
                logger.info(f"[{self.source_name}] No se encontró enlace 'Siguiente'. Fin.")
                break

        logger.info(f"[{self.source_name}] Búsqueda web finalizada. {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers

if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()

    opcionempleo_config = {
        'enabled': True,
        'base_url': 'https://www.opcionempleo.ec/'
    }

    scraper = OpcionempleoScraper(http_client=http_client, config=opcionempleo_config)
    search_params = {
        'keywords': ['contable'],
        'location': 'Quito'
    }

    print(f"\n--- Iniciando prueba de OpcionempleoScraper ---")
    print(f"Buscando trabajos con: {search_params}")

    try:
        ofertas = scraper.fetch_jobs(search_params)
        print(f"\n--- Prueba finalizada ---")
        print(f"Se encontraron {len(ofertas)} ofertas.")

        if ofertas:
            print("\nEjemplo de la primera oferta encontrada:")
            pprint.pprint(ofertas[0])
            print("\nNOTA: La 'url' probablemente enlace a la fuente original.")
            print("      La 'descripcion' probablemente sea corta (snippet) o None.")
        else:
            print("\nNo se encontraron ofertas con los criterios de prueba.")

    except Exception as e:
        logger.exception("Ocurrió un error durante la prueba del scraper Opcionempleo.")
        print(f"\n--- Ocurrió un error durante la prueba: {e} ---")

    finally:
        http_client.close()
