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
from datetime import datetime, timedelta # Para fechas
import re # Por si acaso
from urllib.parse import quote_plus, urljoin # Para URLs

# Nuestras herramientas base
from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

# Logger para este scraper
logger = logging.getLogger(__name__)

# Límite de páginas
MAX_PAGES_TO_SCRAPE_OPCIONEMPLEO = 10 # Ajustable

class OpcionempleoScraper(BaseScraper):
    """
    Implementación del scraper para Opcionempleo (ej: opcionempleo.ec).
    """

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador del scraper de Opcionempleo.

        Args:
            http_client (HTTPClient): Instancia del cliente HTTP.
            config (Optional[Dict[str, Any]]): Config específica (esperamos 'base_url').
        """
        super().__init__(source_name="opcionempleo", http_client=http_client, config=config)

        # URL base por defecto si no está en la config. ¡Verificarla para Ecuador!
        if not self.base_url:
            self.base_url = "https://www.opcionempleo.ec/" # logger.warning(f"[{self.source_name}] 'base_url' no encontrada en config. Usando default: {self.base_url}")


    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        """
        Construye la URL de búsqueda para Opcionempleo.

        Probablemente usa parámetros query como ?s=, &l=, &p=.
        ¡Necesita verificación!

        Args:
            keywords (List[str]): Palabras clave.
            location (str): Ubicación.
            page (int): Número de página (puede empezar en 0 o 1).

        Returns:
            Optional[str]: La URL construida o None.
        """
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        # Preparamos keywords y location.
        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''
        location_query = quote_plus(location) if location else ''

        # --- Lógica URL Opcionempleo ---
        # Asumimos una ruta base y parámetros. ¡A verificar!
        search_path = "/busqueda/empleos" # O "/", "/ofertas/", etc. params = {}
        if keyword_query:
            # ¿Parámetro 's', 'q', 'query'?
            params['s'] = keyword_query # if location_query:
             # ¿Parámetro 'l', 'location', 'ciudad'?
            params['l'] = location_query # # Paginación: ¿Cómo numera las páginas? ¿Empieza en 0 o 1? ¿Parámetro 'p', 'page'?
        if page > 1: # O page > 0 si empieza en 0
            params['p'] = page # query_string = '&'.join([f"{k}={v}" for k, v in params.items()]) if params else ''

        full_url = f"{self.base_url.rstrip('/')}{search_path}"
        if query_string:
            full_url += f"?{query_string}"

        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url

    # Usaremos el _parse_relative_date base si funciona. Adaptar si es necesario.

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Implementación de la búsqueda de trabajos para Opcionempleo.
        """
        logger.info(f"[{self.source_name}] Iniciando búsqueda web con: {search_params}")
        all_job_offers = []
        current_page = 1 # O 0, dependiendo de cómo empiece la paginación
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', 'Quito') # Default

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

            # Encontrar las ofertas. ¡Selector de EJEMPLO! Puede ser article, div.job, li...
            job_cards = soup.select('article.job, div.job-listing') # if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}. Fin.")
                break

            logger.info(f"[{self.source_name}] {len(job_cards)} ofertas encontradas en página {current_page}.")

            for card in job_cards:
                oferta = self.get_standard_job_dict() # Empezamos estándar.

                # --- Extracción de Datos (Opcionempleo) ---
                # ¡Selectores de EJEMPLO! ¡A verificar!

                # Título y Enlace (¡Importante! Suele ser el enlace externo)
                title_link_element = card.select_one('header a, h2 a.job_link') # oferta['titulo'] = self._safe_get_text(title_link_element)
                # Esta URL nos llevará probablemente fuera de Opcionempleo.
                oferta['url'] = self._safe_get_attribute(title_link_element, 'href')
                # Asegurarnos de que sea absoluta. Opcionempleo podría usar URLs absolutas directamente.
                if oferta['url'] and not oferta['url'].startswith('http'):
                     # Si es relativa a Opcionempleo (raro para enlaces externos), la construimos.
                     # Es más probable que ya sea absoluta o una URL de redirección interna. ¡Verificar!
                     oferta['url'] = urljoin(self.base_url, oferta['url'])


                # Empresa
                company_element = card.select_one('p.company, span.job-company') # oferta['empresa'] = self._safe_get_text(company_element)

                # Ubicación
                location_element = card.select_one('p.location, span.job-location') # oferta['ubicacion'] = self._safe_get_text(location_element)

                # Fecha (Suele ser relativa)
                date_element = card.select_one('p.date, span.job-date') # date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text) # Usar parser base (o adaptarlo).

                # Descripción: Tomamos el snippet si existe. La completa está en el enlace externo.
                snippet_element = card.select_one('div.desc, p.job-snippet') # oferta['descripcion'] = self._safe_get_text(snippet_element)

                # Añadimos si tenemos lo básico (título y URL externa).
                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)
                else:
                    logger.warning(f"[{self.source_name}] Oferta omitida por faltar título o URL.")


            # --- Paginación ---
            # Buscar enlace "Siguiente". ¡Selector de EJEMPLO!
            next_page_link_element = soup.select_one('a.next, li.next a') # if next_page_link_element:
                 next_page_href = self._safe_get_attribute(next_page_link_element, 'href')
                 if next_page_href and next_page_href != '#':
                     # Construir URL siguiente. Opcionempleo podría usar URLs absolutas en paginación.
                     if next_page_href.startswith('http'):
                         current_url = next_page_href
                     elif next_page_href.startswith('/'): # Relativa al dominio base
                          current_url = self._build_url(next_page_href)
                     else: # Podría ser relativa a la página actual? Menos común.
                          try:
                               current_url = urljoin(current_url, next_page_href)
                          except Exception:
                               logger.error(f"No se pudo construir URL de paginación desde actual '{current_url}' y relativa '{next_page_href}'")
                               break

                     if not current_url:
                         logger.error(f"[{self.source_name}] No se pudo construir URL siguiente desde href: {next_page_href}")
                         break
                     current_page += 1 # Avanzamos nuestro contador.
                     logger.debug(f"[{self.source_name}] Pasando a página siguiente: {current_url}")
                 else:
                     logger.info(f"[{self.source_name}] Enlace 'Siguiente' no válido. Fin.")
                     break
            else:
                 logger.info(f"[{self.source_name}] No se encontró enlace 'Siguiente'. Fin.")
                 break

        # Fin del bucle while

        logger.info(f"[{self.source_name}] Búsqueda web finalizada. {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers


# --- Ejemplo de uso ---
if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()

    # Config para Opcionempleo Ecuador (¡Verificar URL!)
    opcionempleo_config = {
        'enabled': True,
        'base_url': 'https://www.opcionempleo.ec/'
    }

    scraper = OpcionempleoScraper(http_client=http_client, config=opcionempleo_config)

    # Búsqueda de ejemplo
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