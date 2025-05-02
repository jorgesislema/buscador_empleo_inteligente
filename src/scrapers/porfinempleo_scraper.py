# -*- coding: utf-8 -*-
# /src/scrapers/porfinempleo_scraper.py

"""
Scraper específico para el portal PorfinEmpleo (Ecuador).

Hereda de BaseScraper y contiene la lógica para extraer las ofertas
de porfinempleo.com.

Compañero, ¡a la carga! Toca inspeccionar porfinempleo.com
y ajustar los selectores CSS y la lógica de URL que pongo aquí como
punto de partida. ¡Tú puedes!
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta # Para fechas
import re # Por si acaso
from urllib.parse import quote_plus # Para URLs

# Nuestras herramientas base
from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

# Logger para este scraper
logger = logging.getLogger(__name__)

# Límite de páginas para pruebas
MAX_PAGES_TO_SCRAPE_PORFINEMPLEO = 10 # Ajustar según veas

class PorfinempleoScraper(BaseScraper):
    """
    Implementación del scraper para PorfinEmpleo.com.
    """

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador del scraper de PorfinEmpleo.

        Args:
            http_client (HTTPClient): Instancia del cliente HTTP.
            config (Optional[Dict[str, Any]]): Config específica (esperamos 'base_url').
        """
        super().__init__(source_name="porfinempleo", http_client=http_client, config=config)

        # URL base por defecto si no está en la config. ¡Verificarla!
        if not self.base_url:
            self.base_url = "https://www.porfinempleo.com/" # logger.warning(f"[{self.source_name}] 'base_url' no encontrada en config. Usando default: {self.base_url}")


    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        """
        Construye la URL de búsqueda para PorfinEmpleo.com.

        Asumiremos que usa parámetros query como ?q= &location= &page=.
        ¡Necesita verificación!

        Args:
            keywords (List[str]): Palabras clave.
            location (str): Ubicación.
            page (int): Número de página.

        Returns:
            Optional[str]: La URL construida o None.
        """
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        # Preparamos keywords y location para parámetros URL.
        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''
        # Para la ubicación, quizás necesite el formato exacto (Quito, Pichincha, etc.)
        # O un código específico. Usaremos el texto codificado por ahora.
        location_query = quote_plus(location) if location else ''

        # --- Lógica URL PorfinEmpleo ---
        # Asumimos una ruta base y parámetros. ¡A verificar!
        search_path = "/ofertas-trabajo/" # O "/empleos/", etc. # Construimos los parámetros
        params = {}
        if keyword_query:
            params['q'] = keyword_query # if location_query:
            # ¿Cómo se llama el parámetro de ubicación? ¿location? ¿ciudad? ¿provincia?
            params['location'] = location_query # if page > 1:
            params['page'] = page # # Creamos la query string si hay parámetros.
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()]) if params else ''

        full_url = f"{self.base_url.rstrip('/')}{search_path}"
        if query_string:
            full_url += f"?{query_string}"

        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url

    # Usaremos el _parse_relative_date de BaseScraper si funciona.
    # Si PorfinEmpleo usa fechas diferentes, creamos uno específico aquí.
    # def _parse_porfinempleo_date(self, date_str: Optional[str]) -> Optional[str]: ...

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Implementación de la búsqueda de trabajos para PorfinEmpleo.
        """
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', 'Quito') # Default a Quito

        while current_page <= MAX_PAGES_TO_SCRAPE_PORFINEMPLEO:
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

            # Encontrar las ofertas. ¡Selector de EJEMPLO!
            job_cards = soup.select('div.job-listing, article.offer-card') # if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}. Fin.")
                break

            logger.info(f"[{self.source_name}] {len(job_cards)} ofertas encontradas en página {current_page}.")

            for card in job_cards:
                oferta = self.get_standard_job_dict() # Empezamos estándar.

                # --- Extracción de Datos (PorfinEmpleo) ---
                # ¡Selectores de EJEMPLO! ¡A verificar!

                title_link_element = card.select_one('h2.job-title a, a.offer-link') # oferta['titulo'] = self._safe_get_text(title_link_element)
                detail_url_relative = self._safe_get_attribute(title_link_element, 'href')
                oferta['url'] = self._build_url(detail_url_relative) # Construir URL absoluta.

                company_element = card.select_one('span.company-name, div.company a') # oferta['empresa'] = self._safe_get_text(company_element)

                location_element = card.select_one('span.location, div.job-location') # oferta['ubicacion'] = self._safe_get_text(location_element)

                date_element = card.select_one('span.date, time.post-date') # date_text = self._safe_get_text(date_element)
                # Intentamos con el parser relativo base. Ajustar si es necesario.
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text)

                # --- Visitar Página de Detalle para Descripción ---
                oferta['descripcion'] = None # Inicializar.
                if oferta['url']:
                    logger.debug(f"[{self.source_name}] Visitando detalle: {oferta['url']}")
                    detail_html = self._fetch_html(oferta['url'])
                    detail_soup = self._parse_html(detail_html)
                    if detail_soup:
                        # Buscar el contenedor de la descripción. ¡Selector de EJEMPLO!
                        desc_container = detail_soup.select_one('div.job-description, section.offer-details') # if desc_container:
                             # Intentamos obtener texto limpio del contenedor.
                             oferta['descripcion'] = self._safe_get_text(desc_container)
                             # Quizás necesitemos buscar párrafos <p> si el texto está disperso.
                             # paragraphs = desc_container.find_all('p') ... etc.
                        else:
                            logger.warning(f"[{self.source_name}] No se encontró contenedor de descripción en: {oferta['url']}")
                    else:
                        logger.warning(f"[{self.source_name}] No se pudo parsear detalle para: {oferta['url']}")
                else:
                     logger.warning(f"[{self.source_name}] No URL de detalle para: {oferta['titulo']}")

                # Añadimos si tenemos lo básico.
                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)
                else:
                    logger.warning(f"[{self.source_name}] Oferta omitida por faltar título o URL.")


            # --- Paginación ---
            # Buscar enlace "Siguiente". ¡Selector de EJEMPLO!
            next_page_link_element = soup.select_one('a.next-page, li.pagination-next a') # if next_page_link_element:
                 next_page_href = self._safe_get_attribute(next_page_link_element, 'href')
                 if next_page_href and next_page_href != '#':
                     # Construir URL siguiente. ¡Ojo si es relativa!
                     current_url = self._build_url(next_page_href)
                     if not current_url:
                          logger.error(f"[{self.source_name}] No se pudo construir URL siguiente desde href: {next_page_href}")
                          break
                     current_page += 1
                     logger.debug(f"[{self.source_name}] Pasando a página siguiente: {current_url}")
                 else:
                     logger.info(f"[{self.source_name}] Enlace 'Siguiente' no válido. Fin.")
                     break
            else:
                 logger.info(f"[{self.source_name}] No se encontró enlace 'Siguiente'. Fin.")
                 break

        # Fin del bucle while

        logger.info(f"[{self.source_name}] Búsqueda finalizada. {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers


# --- Ejemplo de uso ---
if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()

    # Config para PorfinEmpleo (¡Verificar URL!)
    porfinempleo_config = {
        'enabled': True,
        'base_url': 'https://www.porfinempleo.com/'
    }

    scraper = PorfinempleoScraper(http_client=http_client, config=porfinempleo_config)

    # Búsqueda de ejemplo
    search_params = {
        'keywords': ['ingeniero', 'sistemas'],
        'location': 'Quito'
    }

    print(f"\n--- Iniciando prueba de PorfinempleoScraper ---")
    print(f"Buscando trabajos con: {search_params}")

    try:
        ofertas = scraper.fetch_jobs(search_params)
        print(f"\n--- Prueba finalizada ---")
        print(f"Se encontraron {len(ofertas)} ofertas.")

        if ofertas:
            print("\nEjemplo de la primera oferta encontrada:")
            pprint.pprint(ofertas[0])
        else:
            print("\nNo se encontraron ofertas con los criterios de prueba.")

    except Exception as e:
        logger.exception("Ocurrió un error durante la prueba del scraper PorfinEmpleo.")
        print(f"\n--- Ocurrió un error durante la prueba: {e} ---")

    finally:
        http_client.close()