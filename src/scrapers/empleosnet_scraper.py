# -*- coding: utf-8 -*-
# /src/scrapers/empleosnet_scraper.py

"""
Scraper para el portal Empleos.net (Latinoamérica).

Este sitio puede variar según el país (empleos.net/cr, /ni, etc.), por lo tanto,
este scraper está diseñado para ser flexible pero comienza con un solo dominio base.

Ajusta selectores específicos según el país o subdominio que utilices.
"""

import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus, urljoin
from datetime import datetime, timedelta
import re

from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE_EMPLEOSNET = 5

class EmpleosNetScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__("empleosnet", http_client=http_client, config=config)
        if not self.base_url:
            self.base_url = "https://www.empleos.net/"
            logger.warning(f"[{self.source_name}] 'base_url' no proporcionada. Usando default: {self.base_url}")

    def _build_search_url(self, keywords: List[str], page: int = 1) -> Optional[str]:
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        query = quote_plus(' '.join(keywords)) if keywords else ''
        page_param = f"&page={page}" if page > 1 else ''
        full_url = f"{self.base_url.rstrip('/')}/empleos?q={query}{page_param}"
        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url

    def _parse_relative_date(self, date_str: str) -> Optional[str]:
        if not date_str:
            return None

        now = datetime.now()
        date_str = date_str.lower().strip()

        if "hoy" in date_str:
            return now.strftime('%Y-%m-%d')
        elif "ayer" in date_str:
            return (now - timedelta(days=1)).strftime('%Y-%m-%d')

        match = re.search(r"hace\s+(\d+)\s+(día|días|semana|semanas|mes|meses)", date_str)
        if match:
            value = int(match.group(1))
            unit = match.group(2)

            if "día" in unit:
                delta = timedelta(days=value)
            elif "semana" in unit:
                delta = timedelta(weeks=value)
            elif "mes" in unit:
                delta = timedelta(days=value * 30)
            else:
                return None

            return (now - delta).strftime('%Y-%m-%d')

        return date_str

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_jobs = []
        current_page = 1
        keywords = search_params.get("keywords", [])

        while current_page <= MAX_PAGES_TO_SCRAPE_EMPLEOSNET:
            url = self._build_search_url(keywords, current_page)
            if not url:
                break

            html = self._fetch_html(url)
            if not html:
                break

            soup = self._parse_html(html)
            if not soup:
                break

            cards = soup.select("div.job-card, div.oferta")
            if not cards:
                break

            for card in cards:
                oferta = self.get_standard_job_dict()
                title_el = card.select_one("h2 a")
                oferta['titulo'] = self._safe_get_text(title_el)
                oferta['url'] = self._build_url(self._safe_get_attribute(title_el, "href"))

                empresa_el = card.select_one(".company")
                oferta['empresa'] = self._safe_get_text(empresa_el)

                ubicacion_el = card.select_one(".location")
                oferta['ubicacion'] = self._safe_get_text(ubicacion_el)

                fecha_el = card.select_one(".date")
                oferta['fecha_publicacion'] = self._parse_relative_date(self._safe_get_text(fecha_el))

                desc_el = card.select_one(".description")
                oferta['descripcion'] = self._safe_get_text(desc_el)

                if oferta['titulo'] and oferta['url']:
                    all_jobs.append(oferta)

            next_page = soup.select_one("a.next")
            if not next_page:
                break

            current_page += 1

        logger.info(f"[{self.source_name}] {len(all_jobs)} ofertas encontradas.")
        return all_jobs
