# -*- coding: utf-8 -*-
# /src/scrapers/soyfreelancer_scraper.py

"""
Scraper específico para la plataforma de freelancing SoyFreelancer.com.

Hereda de BaseScraper y se adapta para extraer *proyectos* freelance,
mapeándolos lo mejor posible a nuestro formato estándar.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re
from urllib.parse import quote_plus, urljoin
import random

from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE_SOYFREELANCER = 5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

class SoyFreelancerScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="soyfreelancer", http_client=http_client, config=config)
        if not self.base_url:
            self.base_url = "https://www.soyfreelancer.com/"
        logger.info(f"[{self.source_name}] Scraper inicializado para buscar PROYECTOS FREELANCE.")

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

        query_string = '&'.join([f"{k}={v}" for k, v in params.items()]) if params else ''
        full_url = f"{self.base_url.rstrip('/')}/proyectos/buscar/"
        if query_string:
            full_url += f"?{query_string}"

        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url

    def _parse_soyfreelancer_date(self, date_str: Optional[str]) -> Optional[str]:
        if not date_str:
            return None
        date_str_lower = date_str.lower().strip()
        now = datetime.now()
        match = re.search(r'(?:hace|publicado hace)\s+(\d+)\s+(hora|horas|día|días|semana|semanas|mes|meses)', date_str_lower)
        if match:
            try:
                value = int(match.group(1))
                unit = match.group(2)
                if unit.startswith('hora'):
                    delta = timedelta(hours=value)
                elif unit.startswith('día'):
                    delta = timedelta(days=value)
                elif unit.startswith('semana'):
                    delta = timedelta(weeks=value)
                elif unit.startswith('mes'):
                    delta = timedelta(days=value * 30)
                else:
                    return date_str
                return (now - delta).date().strftime('%Y-%m-%d')
            except ValueError:
                return date_str
        elif 'hoy' in date_str_lower:
            return now.date().strftime('%Y-%m-%d')
        elif 'ayer' in date_str_lower:
            return (now - timedelta(days=1)).date().strftime('%Y-%m-%d')
        else:
            logger.debug(f"[{self.source_name}] Formato fecha no reconocido: '{date_str}'")
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
        logger.info(f"[{self.source_name}] Iniciando búsqueda de PROYECTOS con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])

        while current_page <= MAX_PAGES_TO_SCRAPE_SOYFREELANCER:
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

            project_cards = soup.select('div.project-item, div.project-card-wrapper, div.project-card, div.project')
            if not project_cards:
                logger.info(f"[{self.source_name}] No se encontraron proyectos en página {current_page}. Fin.")
                break

            logger.info(f"[{self.source_name}] {len(project_cards)} proyectos encontrados en página {current_page}.")

            for card in project_cards:
                oferta = self.get_standard_job_dict()
                oferta['fuente'] = f"{self.source_name} (Freelance)"

                title_link_element = card.select_one('h2.project-title a, a.project-link, a.job-title')
                oferta['titulo'] = self._safe_get_text(title_link_element)
                detail_url_relative = self._safe_get_attribute(title_link_element, 'href')
                oferta['url'] = self._build_url(detail_url_relative)

                client_element = card.select_one('span.client-username, div.client-info a, span.company, div.company')
                oferta['empresa'] = self._safe_get_text(client_element)

                budget_element = card.select_one('span.budget-range, div.project-price, span.salary, div.salary')
                budget_text = self._safe_get_text(budget_element)
                oferta['descripcion'] = f"Presupuesto: {budget_text}" if budget_text else ""

                location_element = card.select_one('span.location, div.client-country, span.location-text, div.location')
                oferta['ubicacion'] = self._safe_get_text(location_element)

                date_element = card.select_one('span.date-published, time.posted-on, span.date, time')
                date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = self._parse_soyfreelancer_date(date_text)

                tags_elements = card.select('a.skill-tag, div.tags span, span.skill, div.skill')
                tags = [self._safe_get_text(tag) for tag in tags_elements if self._safe_get_text(tag)]
                if tags:
                    oferta['descripcion'] = f"{oferta['descripcion']}\nSkills: {', '.join(tags)}".strip()

                if oferta['url']:
                    logger.debug(f"[{self.source_name}] Visitando detalle: {oferta['url']}")
                    detail_html = self._fetch_html_with_retry(oferta['url'])
                    detail_soup = self._parse_html(detail_html)
                    if detail_soup:
                        desc_container = detail_soup.select_one('div.project-description-full, section#project-details, div.description, div.job-desc')
                        full_description = self._safe_get_text(desc_container)
                        if full_description:
                            if budget_text and budget_text not in full_description:
                                full_description = f"Presupuesto: {budget_text}\n\n{full_description}"
                            if tags and "Skills:" not in full_description:
                                full_description += f"\n\nSkills: {', '.join(tags)}"
                            oferta['descripcion'] = full_description
                    else:
                        logger.warning(f"[{self.source_name}] No se pudo parsear detalle para: {oferta['url']}")
                else:
                    logger.warning(f"[{self.source_name}] No URL de detalle para: {oferta['titulo']}")

                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)
                else:
                    logger.warning(f"[{self.source_name}] Proyecto omitido por faltar título o URL.")

            next_page_link_element = soup.select_one('a.pagination-next, li.next a, a.next, a[rel="next"]')
            if next_page_link_element:
                next_page_href = self._safe_get_attribute(next_page_link_element, 'href')
                if next_page_href and next_page_href != '#':
                    try:
                        current_url = next_page_href if next_page_href.startswith('http') else urljoin(current_url, next_page_href)
                    except Exception:
                        logger.error(f"No se pudo construir URL paginación desde '{current_url}' y '{next_page_href}'")
                        break
                    current_page += 1
                    logger.debug(f"[{self.source_name}] Pasando a página siguiente: {current_url}")
                else:
                    logger.info(f"[{self.source_name}] Enlace 'Siguiente' no válido. Fin.")
                    break
            else:
                logger.info(f"[{self.source_name}] No se encontró enlace 'Siguiente'. Fin.")
                break

        logger.info(f"[{self.source_name}] Búsqueda finalizada. {len(all_job_offers)} proyectos freelance encontrados.")
        return all_job_offers


if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()

    soyfreelancer_config = {
        'enabled': True,
        'base_url': 'https://www.soyfreelancer.com/'
    }

    scraper = SoyFreelancerScraper(http_client=http_client, config=soyfreelancer_config)

    search_params = {
        'keywords': ['análisis de datos', 'excel'],
        'location': 'Remote'
    }

    print(f"\n--- Iniciando prueba de SoyFreelancerScraper ---")
    print(f"Buscando proyectos freelance con: {search_params}")

    try:
        ofertas = scraper.fetch_jobs(search_params)
        print(f"\n--- Prueba finalizada ---")
        print(f"Se encontraron {len(ofertas)} proyectos.")

        if ofertas:
            print("\nEjemplo del primer proyecto encontrado:")
            pprint.pprint(ofertas[0])
            print("\nNOTA: 'empresa' es el cliente, 'descripcion' puede incluir presupuesto/skills.")
            print("      'fuente' indica que es Freelance.")
        else:
            print("\nNo se encontraron proyectos con los criterios de prueba.")

    except Exception as e:
        logger.exception("Ocurrió un error durante la prueba del scraper SoyFreelancer.")
        print(f"\n--- Ocurrió un error durante la prueba: {e} ---")

    finally:
        http_client.close()
