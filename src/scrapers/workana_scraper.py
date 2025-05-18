# -*- coding: utf-8 -*-
# /src/scrapers/workana_scraper.py

"""
Scraper para la plataforma de freelancing Workana.
Extrae proyectos freelance y los adapta a un formato de oferta de empleo.
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
MAX_PAGES_TO_SCRAPE_WORKANA = 5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

class WorkanaScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="workana", http_client=http_client, config=config)
        if not self.base_url:
            self.base_url = "https://www.workana.com/"
        logger.info(f"[{self.source_name}] Scraper inicializado para buscar proyectos freelance.")

    def _build_search_url(self, keywords: List[str], page: int = 1) -> Optional[str]:
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''
        params = {}
        if keyword_query:
            params['query'] = keyword_query
        if page > 1:
            params['page'] = page

        search_path = "/es/projects/browse"
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()]) if params else ''
        full_url = f"{self.base_url.rstrip('/')}{search_path}"
        if query_string:
            full_url += f"?{query_string}"

        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url

    def _parse_workana_date(self, date_str: Optional[str]) -> Optional[str]:
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
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])

        while current_page <= MAX_PAGES_TO_SCRAPE_WORKANA:
            logger.info(f"[{self.source_name}] Procesando página {current_page}...")
            current_url = self._build_search_url(keywords, current_page)
            if not current_url:
                logger.error(f"[{self.source_name}] URL inválida. Abortando.")
                break

            html_content = self._fetch_html_with_retry(current_url)
            if not html_content:
                logger.warning(f"[{self.source_name}] No se obtuvo HTML. Fin.")
                break

            soup = self._parse_html(html_content)
            if not soup:
                logger.warning(f"[{self.source_name}] No se pudo parsear HTML. Fin.")
                break

            project_cards = soup.select('div.project-item, div.project-card, div.project-card-wrapper, div.project')
            if not project_cards:
                logger.info(f"[{self.source_name}] No se encontraron proyectos. Fin.")
                break

            for card in project_cards:
                oferta = self.get_standard_job_dict()
                oferta['fuente'] = self.source_name + " (Freelance)"

                title_link = card.select_one('h2 a, div.project-title a, a.project-link, a.job-title')
                oferta['titulo'] = self._safe_get_text(title_link)
                oferta['url'] = self._build_url(self._safe_get_attribute(title_link, 'href'))

                oferta['empresa'] = self._safe_get_text(card.select_one('span.client-name, div.client-info, span.company, div.company'))
                budget_text = self._safe_get_text(card.select_one('span.budget, div.project-budget, span.salary, div.salary'))
                oferta['descripcion'] = f"Presupuesto: {budget_text}" if budget_text else None

                oferta['ubicacion'] = self._safe_get_text(card.select_one('span.location, div.client-location, span.location-text, div.location'))
                date_text = self._safe_get_text(card.select_one('span.date, time.published-on, span.date-published, time'))
                oferta['fecha_publicacion'] = self._parse_workana_date(date_text)

                tags = [self._safe_get_text(tag) for tag in card.select('span.skill-tag, div.tags a, a.skill-tag, div.tags span, span.skill, div.skill') if self._safe_get_text(tag)]
                if tags:
                    skills_str = f"Skills: {', '.join(tags)}"
                    oferta['descripcion'] = f"{oferta['descripcion'] or ''}\n{skills_str}".strip()

                if oferta['url']:
                    detail_html = self._fetch_html_with_retry(oferta['url'])
                    detail_soup = self._parse_html(detail_html)
                    if detail_soup:
                        desc_container = detail_soup.select_one('div.project-description, div#project-details, div.description, div.job-desc')
                        full_description = self._safe_get_text(desc_container)
                        if full_description:
                            oferta['descripcion'] = full_description

                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)
                else:
                    logger.warning(f"[{self.source_name}] Proyecto omitido por faltar título o URL.")

            current_page += 1

        logger.info(f"[{self.source_name}] Búsqueda finalizada. {len(all_job_offers)} proyectos freelance encontrados.")
        return all_job_offers
