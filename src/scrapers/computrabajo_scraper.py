# -*- coding: utf-8 -*-
# /src/scrapers/computrabajo_scraper.py

"""
Scraper específico para Computrabajo Ecuador.
Extrae ofertas de empleo desde https://www.computrabajo.com.ec
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re
from urllib.parse import quote_plus

from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE = 10

class ComputrabajoScraper(BaseScraper):
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="computrabajo", http_client=http_client, config=config)
        if not self.base_url:
            logger.error(f"[{self.source_name}] Falta 'base_url' en la config. El scraper no funcionará correctamente.")

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        if not self.base_url:
            return None
        keyword_query = quote_plus(" ".join(keywords)) if keywords else ""
        location_query = "&p=Pichincha" if location.lower() == "quito" else ""
        search_url = f"{self.base_url}/ofertas-de-trabajo/?q={keyword_query}{location_query}"
        if page > 1:
            search_url += f"&pg={page}"
        return search_url

    def _parse_relative_date(self, date_str: Optional[str]) -> Optional[str]:
        if not date_str:
            return None
        date_str = date_str.lower().strip()
        today = datetime.now().date()
        if "hoy" in date_str:
            return today.strftime('%Y-%m-%d')
        elif "ayer" in date_str:
            return (today - timedelta(days=1)).strftime('%Y-%m-%d')
        match = re.search(r"hace (\d+) días?", date_str)
        if match:
            try:
                days_ago = int(match.group(1))
                return (today - timedelta(days=days_ago)).strftime('%Y-%m-%d')
            except ValueError:
                return date_str
        return date_str

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get("keywords", [])
        location = search_params.get("location", "Quito")

        while current_page <= MAX_PAGES_TO_SCRAPE:
            url = self._build_search_url(keywords, location, current_page)
            if not url:
                break
            html = self._fetch_html(url)
            if not html:
                break
            soup = self._parse_html(html)
            if not soup:
                break
            job_cards = soup.select("article.box_offer")
            if not job_cards:
                break

            for card in job_cards:
                oferta = self.get_standard_job_dict()
                title_element = card.select_one("h1.js-o-link a, p.title a")
                oferta["titulo"] = self._safe_get_text(title_element)
                oferta["url"] = self._build_url(self._safe_get_attribute(title_element, "href"))
                oferta["empresa"] = self._safe_get_text(card.select_one("div.fs16 a, span.d-block a"))
                oferta["ubicacion"] = self._safe_get_text(card.select_one("p span:not([class]), span span[title]"))
                date_text = self._safe_get_text(card.select_one("span.fc_aux, p.fs13 span"))
                oferta["fecha_publicacion"] = self._parse_relative_date(date_text)

                if oferta["url"]:
                    detail_html = self._fetch_html(oferta["url"])
                    detail_soup = self._parse_html(detail_html)
                    if detail_soup:
                        desc_element = detail_soup.select_one("section#description > div > p, div.fs16")
                        oferta["descripcion"] = self._safe_get_text(desc_element)

                if oferta["titulo"] and oferta["url"]:
                    all_job_offers.append(oferta)

            current_page += 1

        logger.info(f"[{self.source_name}] Se encontraron {len(all_job_offers)} ofertas.")
        return all_job_offers


if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()
    config = {'base_url': 'https://www.computrabajo.com.ec'}
    scraper = ComputrabajoScraper(http_client=http_client, config=config)

    params = {'keywords': ['data', 'analista'], 'location': 'Quito'}
    ofertas = scraper.fetch_jobs(params)
    pprint.pprint(ofertas[:1])
    http_client.close()
