# -*- coding: utf-8 -*-
# /src/scrapers/justremote_scraper.py
"""
Scraper para JustRemote.co: extrae ofertas de trabajo remoto.
Ajustar selectores si el sitio cambia estructura.
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
MAX_PAGES_TO_SCRAPE_JUSTREMOTE = 5

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

class JustRemoteScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="justremote", http_client=http_client, config=config)
        if not self.base_url:
            self.base_url = "https://justremote.co/"
            logger.info(f"[{self.source_name}] Usando base_url por defecto: {self.base_url}")

    def _build_search_url(self, keywords: List[str], page: int = 1) -> Optional[str]:
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin base_url.")
            return None
        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''
        search_url = f"{self.base_url.rstrip('/')}/remote-jobs/search?term={keyword_query}" if keyword_query else f"{self.base_url.rstrip('/')}/remote-jobs"
        if page > 1:
            search_url += f"&page={page}"
        logger.debug(f"[{self.source_name}] URL construida: {search_url}")
        return search_url

    def _fetch_html_with_retry(self, url, max_retries=3):
        for attempt in range(max_retries):
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            html = self._fetch_html(url, headers=headers)
            if html:
                return html
            logger.warning(f"[{self.source_name}] Reintento {attempt+1} fallido para {url}")
        logger.error(f"[{self.source_name}] Fallaron todos los reintentos para {url}")
        return None

    def _parse_relative_date(self, date_str: Optional[str]) -> Optional[str]:
        if not date_str:
            return None
        date_str_lower = date_str.lower().strip()
        now = datetime.now()
        match = re.search(r'(?:hace|posted)\s*(\d+)\s*(day|days|hour|hours|week|weeks|month|months)', date_str_lower)
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            if 'hour' in unit:
                delta = timedelta(hours=value)
            elif 'day' in unit:
                delta = timedelta(days=value)
            elif 'week' in unit:
                delta = timedelta(weeks=value)
            elif 'month' in unit:
                delta = timedelta(days=value * 30)
            else:
                return date_str
            return (now - delta).strftime('%Y-%m-%d')
        elif 'today' in date_str_lower:
            return now.strftime('%Y-%m-%d')
        elif 'yesterday' in date_str_lower:
            return (now - timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            return date_str

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])

        while current_page <= MAX_PAGES_TO_SCRAPE_JUSTREMOTE:
            logger.info(f"[{self.source_name}] Procesando página {current_page}...")
            current_url = self._build_search_url(keywords, current_page)
            if not current_url:
                break
            html_content = self._fetch_html_with_retry(current_url)
            if not html_content:
                break
            soup = self._parse_html(html_content)
            if not soup:
                break
            job_cards = soup.select('div.job-listing, div.job-card, li.job-item, article.job')
            if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}. Fin.")
                break
            for card in job_cards:
                oferta = self.get_standard_job_dict()
                title_link = card.select_one('a.job-title, h2 a, a.job-link')
                oferta['titulo'] = self._safe_get_text(title_link)
                oferta['url'] = self._safe_get_attribute(title_link, 'href')
                if oferta['url'] and oferta['url'].startswith('/'):
                    oferta['url'] = urljoin(self.base_url, oferta['url'])
                company = card.select_one('span.company, div.company, span.company-name')
                oferta['empresa'] = self._safe_get_text(company)
                location = card.select_one('span.location, div.location, span.region')
                oferta['ubicacion'] = self._safe_get_text(location)
                date = card.select_one('span.date, time, span.posted-date')
                date_text = self._safe_get_text(date)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text)
                tags = card.select('span.tag, div.tags a, span.skill, div.skill')
                tags_texts = [self._safe_get_text(tag) for tag in tags if self._safe_get_text(tag)]
                oferta['descripcion'] = f"Tags: {', '.join(tags_texts)}" if tags_texts else None
                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)
                else:
                    logger.warning(f"[{self.source_name}] Oferta omitida por falta de datos suficientes.")
            next_page_link = soup.select_one('a.next_page, li.pagination-next a, a.next, a[rel="next"]')
            if next_page_link:
                next_page_href = self._safe_get_attribute(next_page_link, 'href')
                if next_page_href and next_page_href != '#':
                    current_page += 1
                    continue
            break
        logger.info(f"[{self.source_name}] Búsqueda finalizada. {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers
