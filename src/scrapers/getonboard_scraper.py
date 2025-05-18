# -*- coding: utf-8 -*-
# /src/scrapers/getonboard_scraper.py

"""
Scraper específico para el portal Get on Board (getonboard.com / .co).

Hereda de BaseScraper y se enfoca en extraer ofertas de empleo del
sector tecnológico y digital, populares en LATAM y España.
"""

import logging
import random
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import quote_plus

from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE_GETONBOARD = 10

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

class GetonboardScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="getonboard", http_client=http_client, config=config)
        if not self.base_url:
            self.base_url = "https://www.getonboard.com/"

    def _build_search_url(self, keywords: List[str], page: int = 1) -> Optional[str]:
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''
        params = {}
        if keyword_query:
            params['q'] = keyword_query
        if page > 1:
            params['page'] = page

        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        full_url = f"{self.base_url.rstrip('/')}/jobs"
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

        while current_page <= MAX_PAGES_TO_SCRAPE_GETONBOARD:
            logger.info(f"[{self.source_name}] Procesando página {current_page}...")
            current_url = self._build_search_url(keywords, current_page)
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

            job_cards = soup.select('article.gb-job-card, div.job-container, div.job-card, div.job')
            if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}. Fin.")
                break

            logger.info(f"[{self.source_name}] {len(job_cards)} ofertas encontradas en página {current_page}.")

            for card in job_cards:
                oferta = self.get_standard_job_dict()
                title_link_element = card.select_one('a[data-gtm="title"], h2.job-title a, a.job-title')
                detail_url_relative = self._safe_get_attribute(title_link_element, 'href')
                oferta['url'] = self._build_url(detail_url_relative)
                oferta['titulo'] = self._safe_get_text(title_link_element)

                company_element = card.select_one('a[data-gtm="company"], span.company-name, span.company, div.company')
                oferta['empresa'] = self._safe_get_text(company_element)

                location_element = card.select_one('span.location-tag, div.job-location, span.location, div.location')
                oferta['ubicacion'] = self._safe_get_text(location_element)

                date_element = card.select_one('time, span.publication-date, span.date, time')
                date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = date_text

                salary_element = card.select_one('span.salary-tag, div.job-salary, span.salary, div.salary')
                oferta['salario'] = self._safe_get_text(salary_element)

                oferta['descripcion'] = None
                if oferta['url']:
                    detail_html = self._fetch_html_with_retry(oferta['url'])
                    detail_soup = self._parse_html(detail_html)
                    if detail_soup:
                        desc_container = detail_soup.select_one('div[data-gtm="description"], div.job-description-section, div.description, div.job-desc')
                        if desc_container:
                            oferta['descripcion'] = self._safe_get_text(desc_container)

                        skills_container = detail_soup.select('div#job-requirements ul li, div.skills-section li')
                        skills = [self._safe_get_text(li) for li in skills_container if self._safe_get_text(li)]
                        if skills:
                            oferta['descripcion'] = (oferta['descripcion'] or '') + f"\n\nSkills: {', '.join(skills)}"

                        salary_detail_element = detail_soup.select_one('div.salary-details, div.salary-detail')
                        if salary_detail_element:
                            salary_detail_text = self._safe_get_text(salary_detail_element)
                            if salary_detail_text:
                                oferta['salario'] = salary_detail_text

                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)
                else:
                    logger.warning(f"[{self.source_name}] Oferta omitida por faltar título o URL.")

            current_page += 1

        logger.info(f"[{self.source_name}] Búsqueda finalizada. {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers


if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()

    getonboard_config = {
        'enabled': True,
        'base_url': 'https://www.getonboard.com/'
    }

    scraper = GetonboardScraper(http_client=http_client, config=getonboard_config)
    search_params = {
        'keywords': ['data analyst', 'python'],
        'location': 'Remote'
    }

    ofertas = scraper.fetch_jobs(search_params)
    print(f"Se encontraron {len(ofertas)} ofertas.")
    if ofertas:
        pprint.pprint(ofertas[0])

    http_client.close()
