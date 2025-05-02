# -*- coding: utf-8 -*-
# /src/scrapers/infojobs_scraper.py

"""
Scraper específico para el portal InfoJobs (España).

Hereda de BaseScraper y se encarga de la lógica particular
para extraer ofertas de infojobs.net.

Recordatorio amistoso: La estructura de InfoJobs puede cambiar.
Los selectores CSS aquí son nuestra mejor suposición inicial y
¡NECESITARÁN ser verificados y probablemente ajustados por ti, compañero!
¡A inspeccionar el HTML con las herramientas del navegador!
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re # Para parsear fechas o limpiar texto si es necesario.
from urllib.parse import quote_plus # Para codificar parámetros URL.

# Importamos nuestra base y el cliente HTTP.
from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

# Nuestro logger para este scraper.
logger = logging.getLogger(__name__)

# Límite de páginas por seguridad.
MAX_PAGES_TO_SCRAPE_INFOJOBS = 10 # Ajustar según necesidad.

class InfojobsScraper(BaseScraper):
    """
    Implementación del scraper para InfoJobs.net.
    """

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador del scraper de InfoJobs.

        Args:
            http_client (HTTPClient): Instancia del cliente HTTP.
            config (Optional[Dict[str, Any]]): Config específica para InfoJobs.
                                                Esperamos 'base_url' (ej: 'https://www.infojobs.net').
        """
        super().__init__(source_name="infojobs", http_client=http_client, config=config)
        # Infojobs suele requerir una URL base como 'https://www.infojobs.net'.
        if not self.base_url or 'infojobs.net' not in self.base_url:
            logger.error(f"[{self.source_name}] La 'base_url' en la configuración no parece válida para InfoJobs. Se esperaba algo como 'https://www.infojobs.net'.")
            # Podríamos lanzar un error o intentar usar un default. Por ahora, advertimos.

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        """
        Construye la URL de búsqueda para InfoJobs.net.

        InfoJobs puede usar parámetros como 'keyword', 'provinceName', 'teleworking'.
        ¡Esta lógica necesita verificación con la web real!

        Args:
            keywords (List[str]): Lista de palabras clave.
            location (str): La ubicación (ej: "Remote Spain", "Madrid").
            page (int): El número de página.

        Returns:
            Optional[str]: La URL construida o None si falta la URL base.
        """
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL de búsqueda sin 'base_url'.")
            return None

        # Unimos y codificamos keywords.
        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''

        # --- Lógica de Ubicación/Remoto para InfoJobs ---
        # ¡Esto es una suposición y necesita validación!
        location_params = {}
        is_remote_search = False
        if location:
            loc_lower = location.lower()
            # Detectamos si es búsqueda remota por nuestros términos estándar.
            if any(term in loc_lower for term in ['remote', 'remoto', 'teletrabajo']):
                is_remote_search = True
                # InfoJobs podría tener un parámetro específico para teletrabajo.
                location_params['teleworking'] = 'true' # else:
                 # Si no es remoto, asumimos que es una provincia o ciudad.
                 # InfoJobs podría usar 'provinceName' o similar.
                 # Usaremos la cadena de ubicación directamente por ahora.
                 location_params['provinceName'] = quote_plus(location) # # Construimos la URL base de búsqueda (puede variar).
        # Ejemplo: https://www.infojobs.net/jobsearch/search-results/list.xhtml
        search_base = f"{self.base_url.rstrip('/')}/jobsearch/search-results/list.xhtml" # # Construimos los parámetros de la query string.
        query_params = {
            'keyword': keyword_query,
            'page': page,
            # Añadimos los parámetros de ubicación/remoto que determinamos.
            **location_params
        }
        # Quitamos parámetros vacíos.
        query_params = {k: v for k, v in query_params.items() if v}

        # Creamos la query string (ej: "keyword=python&page=1&teleworking=true")
        query_string = '&'.join([f"{k}={v}" for k, v in query_params.items()])

        full_url = f"{search_base}?{query_string}"
        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url


    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Implementación de la búsqueda de trabajos para InfoJobs.
        """
        logger.info(f"[{self.source_name}] Iniciando búsqueda de trabajos con parámetros: {search_params}")
        all_job_offers = []
        current_page = 1

        keywords = search_params.get('keywords', [])
        # Para InfoJobs, si buscamos remoto, pongamos 'Remote Spain' como referencia.
        # Si no, podríamos usar una ubicación por defecto o la primera de la lista.
        location_input = search_params.get('location', 'Remote Spain') # Default a remoto si no se especifica.

        while current_page <= MAX_PAGES_TO_SCRAPE_INFOJOBS:
            logger.info(f"[{self.source_name}] Procesando página {current_page}...")

            current_url = self._build_search_url(keywords, location_input, current_page)
            if not current_url:
                logger.error(f"[{self.source_name}] No se pudo construir la URL para la página {current_page}. Abortando.")
                break

            html_content = self._fetch_html(current_url)
            if not html_content:
                logger.warning(f"[{self.source_name}] No se pudo obtener HTML de la página {current_page}. Terminando paginación.")
                break

            soup = self._parse_html(html_content)
            if not soup:
                 logger.warning(f"[{self.source_name}] No se pudo parsear HTML de la página {current_page}. Terminando paginación.")
                 break

            # Encontrar las tarjetas de oferta. ¡Selector de EJEMPLO!
            job_cards = soup.select('li.ij-OfferCardCont') # if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en la página {current_page}. Parece que es la última página o no hay resultados.")
                break

            logger.info(f"[{self.source_name}] Encontradas {len(job_cards)} ofertas en la página {current_page}.")

            for card in job_cards:
                oferta = self.get_standard_job_dict() # Empezamos con el estándar.

                # --- Extracción de Datos de la Tarjeta (InfoJobs) ---
                # ¡Todos estos selectores son EJEMPLOS y necesitan verificación!

                title_link_element = card.select_one('h2.ij-OfferCardContent-description-title a') # oferta['titulo'] = self._safe_get_text(title_link_element)
                detail_url = self._safe_get_attribute(title_link_element, 'href')
                # InfoJobs a veces usa URLs relativas al protocolo (//...), asegurémonos de que tengan https:
                if detail_url and detail_url.startswith('//'):
                    detail_url = f"https:{detail_url}"
                elif detail_url and not detail_url.startswith('http'):
                     # Si es relativa a la base, la construimos. ¡Verificar esto!
                     detail_url = self._build_url(detail_url) # Puede necesitar ajustes.
                oferta['url'] = detail_url

                company_element = card.select_one('h3.ij-OfferCardContent-description-ellipsis a, h3.ij-OfferCardContent-description-ellipsis') # oferta['empresa'] = self._safe_get_text(company_element)

                # La ubicación puede estar en un 'li' específico.
                location_element = card.select_one('li.ij-OfferCardContent-description-list-item:-soup-contains("Ubicación:") span, li:has(svg[name="location"]) span') # oferta['ubicacion'] = self._safe_get_text(location_element)

                # Fecha - suele ser relativa.
                date_element = card.select_one('span.ij-OfferCardContent-description-date span, time') # date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text) # Usamos helper de BaseScraper

                # InfoJobs a menudo muestra el salario en la lista.
                salary_element = card.select_one('li.ij-OfferCardContent-description-list-item:-soup-contains("Salario:") span, li:has(svg[name="salary"]) span') # oferta['salario'] = self._safe_get_text(salary_element) # Añadimos salario a nuestro dict estándar (necesitará definirse si lo queremos siempre)

                # Descripción: InfoJobs puede tener un snippet en la tarjeta, o necesitaríamos ir al detalle.
                # Por simplicidad ahora, no iremos a la página de detalle.
                # Si quisiéramos el snippet:
                # snippet_element = card.select_one('p.ij-OfferCardContent-description-description') # # oferta['descripcion'] = self._safe_get_text(snippet_element)
                # Si quisiéramos la descripción completa (requiere visita a detalle):
                # if oferta['url']: ... fetch/parse detail_url ... extract description ...
                oferta['descripcion'] = None # Dejar vacío por ahora.

                # Añadimos la oferta si tenemos lo básico.
                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)
                else:
                     logger.warning(f"[{self.source_name}] Oferta omitida por faltar título o URL.")

            # --- Paginación ---
            # Buscamos el enlace "Siguiente". ¡Selector de ejemplo!
            next_page_link_element = soup.select_one('a.ij-Pagination-link--next') # if next_page_link_element:
                next_page_href = self._safe_get_attribute(next_page_link_element, 'href')
                if next_page_href:
                    # Necesitamos construir la URL completa para la siguiente página.
                    # Puede ser relativa o absoluta.
                    # ¡Ojo! A veces el href es solo '#', indicando que no hay más.
                    if next_page_href == '#':
                         logger.info(f"[{self.source_name}] Enlace 'Siguiente' apunta a '#'. Asumiendo fin de paginación.")
                         break # Salir del bucle
                    # Construimos la URL absoluta si es necesario (urljoin es más robusto para esto).
                    # from urllib.parse import urljoin
                    # current_url = urljoin(self.base_url, next_page_href) # Forma más segura
                    # O usamos nuestro helper si es relativa simple:
                    current_url = self._build_url(next_page_href) # Puede necesitar ajustes.
                    current_page += 1 # Incrementamos el contador manual por si acaso.
                    logger.debug(f"[{self.source_name}] Pasando a la siguiente página: {current_url}")
                else:
                    logger.info(f"[{self.source_name}] No se encontró 'href' en el enlace 'Siguiente'. Terminando paginación.")
                    break # Salir si no hay href
            else:
                 logger.info(f"[{self.source_name}] No se encontró enlace 'Siguiente'. Asumiendo fin de paginación.")
                 break # Salir si no hay enlace

        # Fin del bucle while

        logger.info(f"[{self.source_name}] Búsqueda finalizada. Se encontraron {len(all_job_offers)} ofertas en total.")
        return all_job_offers


# --- Ejemplo de uso ---
if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint # Para imprimir bonito

    setup_logging()
    http_client = HTTPClient()

    # Config para InfoJobs España
    infojobs_config = {
        'enabled': True,
        'base_url': 'https://www.infojobs.net'
    }

    scraper = InfojobsScraper(http_client=http_client, config=infojobs_config)

    # Búsqueda de ejemplo (Remoto en España para 'python data')
    search_params = {
        'keywords': ['python', 'data'],
        'location': 'Remote Spain' # O 'Madrid', 'Barcelona', etc.
    }

    print(f"\n--- Iniciando prueba de InfojobsScraper ---")
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
        logger.exception("Ocurrió un error durante la prueba del scraper InfoJobs.")
        print(f"\n--- Ocurrió un error durante la prueba: {e} ---")

    finally:
        http_client.close()