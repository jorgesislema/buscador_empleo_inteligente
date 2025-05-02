# -*- coding: utf-8 -*-
# /src/scrapers/jooble_scraper.py

"""
Scraper específico para el portal Jooble.

Hereda de BaseScraper e intenta extraer ofertas de la web de Jooble
(ej: ec.jooble.org para Ecuador).

**Advertencia importante, compañero:** Jooble tiene una API oficial.
Scrapear su web es menos fiable y podría ir contra sus términos.
Además, como agregador, puede que solo obtengamos datos básicos y
un enlace a la fuente original. ¡Procedemos con cautela!
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta # Para fechas
import re # Para parsear fechas/texto
from urllib.parse import quote_plus # Para URLs

# Nuestras clases base y utilidades
from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

# Logger para este scraper
logger = logging.getLogger(__name__)

# Límite de páginas
MAX_PAGES_TO_SCRAPE_JOOBLE = 5 # Empezar con pocas para probar

class JoobleScraper(BaseScraper):
    """
    Implementación del scraper para la web de Jooble.
    """

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador del scraper de Jooble.

        Args:
            http_client (HTTPClient): Instancia del cliente HTTP.
            config (Optional[Dict[str, Any]]): Config específica (esperamos 'base_url').
        """
        super().__init__(source_name="jooble", http_client=http_client, config=config)

        # Definimos la URL base por defecto si no está en la config.
        # ¡Asegúrate de que sea la correcta para la región que buscas (ej: Ecuador)!
        if not self.base_url:
            self.base_url = "https://ec.jooble.org" # logger.warning(f"[{self.source_name}] 'base_url' no encontrada en config. Usando default: {self.base_url}")

        logger.warning(f"[{self.source_name}] Iniciando scraper para Jooble. Recuerda que usar la API oficial de Jooble es generalmente preferible.")

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        """
        Construye la URL de búsqueda para la web de Jooble.

        Puede usar rutas como /jobs-{keyword}/{location}?page={N} o parámetros.
        ¡Necesita verificación!

        Args:
            keywords (List[str]): Lista de palabras clave.
            location (str): La ubicación.
            page (int): Número de página.

        Returns:
            Optional[str]: La URL construida o None.
        """
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        # Unimos keywords con '+'.
        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''
        # Preparamos location slug (minúsculas, guiones).
        location_slug = quote_plus(location.lower().replace(" ", "-")) if location else ''

        # --- Lógica URL para Jooble Web ---
        # EJEMPLO 1: Usando parámetros q y l
        # path = "/trabajo" # O la ruta base de búsqueda # params = {'q': keyword_query, 'l': location_slug, 'p': page}
        # query_string = '&'.join([f"{k}={v}" for k, v in params.items() if v])
        # search_url = f"{self.base_url.rstrip('/')}{path}?{query_string}"

        # EJEMPLO 2: Usando path structure /jobs-keyword/location
        # ¡Esto es una suposición fuerte!
        path_parts = ["jobs"] # if keyword_query:
            path_parts.append(f"-{keyword_query}") # Asumiendo formato jobs-keyword
        if location_slug:
             # ¿Cómo añade la ubicación? ¿jobs-keyword/location? ¿jobs-keyword-location?
             path_parts.append(f"/{location_slug}") # path = "".join(path_parts)
        # ¿Paginación en path o parámetro? Asumamos parámetro 'p'.
        page_param = f"?p={page}" if page > 1 else "" # search_url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}{page_param}"


        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {search_url}")
        return search_url

    # Podríamos reutilizar el parser de fechas relativo de BaseScraper si aplica.
    # Si Jooble usa otro formato, necesitaríamos uno específico aquí.
    # def _parse_jooble_date(self, date_str: Optional[str]) -> Optional[str]: ...

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Implementación de la búsqueda de trabajos para Jooble Web.
        """
        logger.info(f"[{self.source_name}] Iniciando búsqueda web con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', 'Quito') # Default a Quito

        while current_page <= MAX_PAGES_TO_SCRAPE_JOOBLE:
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

            # Encontrar las ofertas. ¡Selector de EJEMPLO! Jooble usa 'article' a menudo.
            job_cards = soup.select('article[data-test-id="vacancy-snippet"]') # if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}. Fin.")
                break

            logger.info(f"[{self.source_name}] {len(job_cards)} ofertas encontradas en página {current_page}.")

            for card in job_cards:
                oferta = self.get_standard_job_dict() # Empezamos estándar.

                # --- Extracción de Datos (Jooble Web) ---
                # ¡Selectores de EJEMPLO! ¡A verificar!

                # Título y Enlace (MUY importante, suele ser el enlace a la fuente original)
                # A veces el enlace está en el título, otras en un botón "Ver oferta".
                title_element = card.select_one('h2 a, div[data-test-id="vacancy-title"] a') # link_element = title_element # Asumir que el título tiene el link.
                # Podría haber un botón/link aparte:
                # apply_link_element = card.select_one('a.apply-button-selector') # # if apply_link_element: link_element = apply_link_element

                oferta['titulo'] = self._safe_get_text(title_element)
                # ¡Esta URL es clave! Puede ser a Jooble o directa a la fuente.
                oferta['url'] = self._safe_get_attribute(link_element, 'href')
                # A veces Jooble usa redirecciones. La URL puede ser interna de Jooble primero.
                # Podríamos necesitar construirla absoluta si es relativa.
                # oferta['url'] = self._build_url(oferta['url'])

                # Empresa
                company_element = card.select_one('span[data-test-id="company-name"], div.company-name') # oferta['empresa'] = self._safe_get_text(company_element)

                # Ubicación
                location_element = card.select_one('div[data-test-id="location"] span, div.location') # oferta['ubicacion'] = self._safe_get_text(location_element)

                # Fecha (Suele ser relativa)
                date_element = card.select_one('div.date-text, span.date') # date_text = self._safe_get_text(date_element)
                # Usamos el parser relativo base. ¡Verificar si funciona!
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text)

                # Descripción: Muy probablemente NO esté completa en Jooble.
                # Podríamos tomar un snippet si existe.
                snippet_element = card.select_one('div.description-snippet, span.job-description') # oferta['descripcion'] = self._safe_get_text(snippet_element) # Será corto o None.

                # Fuente Original (A veces Jooble indica de dónde sacó la oferta)
                # source_element = card.select_one('span.original-source') # # original_source = self._safe_get_text(source_element)
                # Podríamos añadir un campo 'fuente_original' o añadirlo a la descripción.
                # if original_source:
                #     oferta['descripcion'] = f"{oferta['descripcion']}\n(Fuente original: {original_source})"


                # Añadimos si tenemos lo básico (título y URL son cruciales aquí).
                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)
                else:
                    logger.warning(f"[{self.source_name}] Oferta omitida por faltar título o URL.")

            # --- Paginación ---
            # Buscar enlace "Siguiente". ¡Selector de EJEMPLO!
            next_page_link_element = soup.select_one('a[data-test-id="pagination-item-next"], a.pagination-next') # if next_page_link_element:
                 next_page_href = self._safe_get_attribute(next_page_link_element, 'href')
                 if next_page_href and next_page_href != '#':
                     current_url = self._build_url(next_page_href) # Construir URL absoluta si es relativa.
                     if not current_url: # Si _build_url falla (ej, no hay base_url)
                          logger.error(f"[{self.source_name}] No se pudo construir la URL para la siguiente página desde href: {next_page_href}")
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

        logger.info(f"[{self.source_name}] Búsqueda web finalizada. {len(all_job_offers)} ofertas encontradas.")
        return all_job_offers


# --- Ejemplo de uso ---
if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint

    setup_logging()
    http_client = HTTPClient()

    # Config para Jooble Ecuador (¡Verificar URL!)
    jooble_config = {
        'enabled': True,
        'base_url': 'https://ec.jooble.org'
    }

    scraper = JoobleScraper(http_client=http_client, config=jooble_config)

    # Búsqueda de ejemplo
    search_params = {
        'keywords': ['desarrollador', 'python'],
        'location': 'Quito'
    }

    print(f"\n--- Iniciando prueba de JoobleScraper ---")
    print(f"(Recordatorio: Se recomienda usar la API de Jooble en lugar de este scraper)")
    print(f"Buscando trabajos con: {search_params}")

    try:
        ofertas = scraper.fetch_jobs(search_params)
        print(f"\n--- Prueba finalizada ---")
        print(f"Se encontraron {len(ofertas)} ofertas.")

        if ofertas:
            print("\nEjemplo de la primera oferta encontrada:")
            pprint.pprint(ofertas[0])
            print("\nNOTA: La 'url' probablemente enlace a la fuente original o a una página intermedia de Jooble.")
            print("      La 'descripcion' probablemente sea corta o None.")
        else:
            print("\nNo se encontraron ofertas con los criterios de prueba.")

    except Exception as e:
        logger.exception("Ocurrió un error durante la prueba del scraper Jooble.")
        print(f"\n--- Ocurrió un error durante la prueba: {e} ---")

    finally:
        http_client.close()