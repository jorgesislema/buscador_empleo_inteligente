# -*- coding: utf-8 -*-
# /src/scrapers/infojobs_scraper.py

"""
Scraper específico para InfoJobs (España).
Extrae ofertas del sector tecnológico adaptándolas a nuestro formato estándar.

Compañero scraper, InfoJobs requiere cuidado con los selectores.
¡Inspecciona bien con F12 y mantén esto actualizado!
"""

import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus, urljoin
from datetime import datetime
from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE_INFOJOBS = 5

class InfojobsScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="infojobs", http_client=http_client, config=config)
        if not self.base_url:
            self.base_url = "https://www.infojobs.net/"
            logger.warning(f"[{self.source_name}] 'base_url' no encontrada. Usando default: {self.base_url}")

    def _build_search_url(self, keywords: List[str], page: int = 1) -> Optional[str]:
        if not self.base_url:
            return None

        query = quote_plus(" ".join(keywords)) if keywords else ""
        path = "/jobsearch/search-results/list.xhtml"  # Path típico
        params = f"?keyword={query}&page={page}"

        full_url = f"{self.base_url.rstrip('/')}{path}{params}"
        logger.debug(f"[{self.source_name}] URL construida: {full_url}")
        return full_url

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Iniciando scraping con parámetros: {search_params}")
        all_offers = []
        keywords = search_params.get("keywords", [])
        current_page = 1

        while current_page <= MAX_PAGES_TO_SCRAPE_INFOJOBS:
            url = self._build_search_url(keywords, page=current_page)
            if not url:
                break

            html = self._fetch_html(url)
            if not html:
                break

            soup = self._parse_html(html)
            job_cards = soup.select("div.elemento")  # Selector típico de tarjeta de oferta

            if not job_cards:
                logger.info(f"[{self.source_name}] No hay más ofertas en página {current_page}.")
                break

            for card in job_cards:
                oferta = self.get_standard_job_dict()
                oferta['fuente'] = self.source_name

                title_element = card.select_one("a.js-o-link")  # Selector de título
                oferta["titulo"] = self._safe_get_text(title_element)
                href = self._safe_get_attribute(title_element, "href")
                oferta["url"] = self._build_url(href)

                empresa_element = card.select_one("span.nom-emp")  # Nombre de la empresa
                oferta["empresa"] = self._safe_get_text(empresa_element)

                ubicacion_element = card.select_one("span.location")  # Ubicación
                oferta["ubicacion"] = self._safe_get_text(ubicacion_element)

                fecha_element = card.select_one("span.date")  # Fecha de publicación
                oferta["fecha_publicacion"] = datetime.today().strftime("%Y-%m-%d")  # Por ahora asumimos "hoy"

                desc_element = card.select_one("div.description")
                oferta["descripcion"] = self._safe_get_text(desc_element)

                if oferta["titulo"] and oferta["url"]:
                    all_offers.append(oferta)
                else:
                    logger.debug(f"[{self.source_name}] Oferta descartada por datos incompletos")

            current_page += 1

        logger.info(f"[{self.source_name}] Total de ofertas obtenidas: {len(all_offers)}")
        return all_offers


