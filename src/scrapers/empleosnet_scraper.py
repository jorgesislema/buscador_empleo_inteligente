# -*- coding: utf-8 -*-
# /src/scrapers/empleosnet_scraper.py

"""
Scraper específico para el portal Empleos.net.

Hereda de BaseScraper y adapta la lógica para este portal,
que parece cubrir varios países de habla hispana. Tendremos
especial cuidado en cómo filtramos por país/ubicación.

Compañero, ¡la misión de siempre! Revisa la web de empleos.net,
inspecciona su HTML y ajusta los selectores y la lógica de URL/país.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta # Para fechas
import re # Por si acaso
from urllib.parse import quote_plus, urljoin, urlparse # Para URLs

# Nuestras herramientas base
from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

# Logger para este scraper
logger = logging.getLogger(__name__)

# Límite de páginas
MAX_PAGES_TO_SCRAPE_EMPLEOSNET = 10 # Ajustable

class EmpleosNetScraper(BaseScraper):
    """
    Implementación del scraper para Empleos.net.
    """

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador del scraper de Empleos.net.

        Args:
            http_client (HTTPClient): Instancia del cliente HTTP.
            config (Optional[Dict[str, Any]]): Config específica (esperamos 'base_url').
        """
        super().__init__(source_name="empleosnet", http_client=http_client, config=config)

        # URL base por defecto si no está en la config.
        if not self.base_url:
            self.base_url = "https://www.empleos.net/" # logger.warning(f"[{self.source_name}] 'base_url' no encontrada en config. Usando default: {self.base_url}")

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        """
        Construye la URL de búsqueda para Empleos.net.

        Puede usar parámetros como ?q=, &pais=, &provincia=, &page=.
        ¡Necesita verificación!

        Args:
            keywords (List[str]): Palabras clave.
            location (str): Ubicación (puede incluir país o ser "Remote").
            page (int): Número de página.

        Returns:
            Optional[str]: La URL construida o None.
        """
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        # Preparamos keywords y location.
        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''
        location_query = quote_plus(location) if location else ''

        # --- Lógica URL Empleos.net ---
        # Asumimos una ruta base y parámetros. ¡A verificar!
        search_path = "/trabajos/" # O "/buscar/", "/empleo/"? params = {}
        if keyword_query:
            # ¿Parámetro 'q', 'keyword', 'palabra'?
            params['q'] = keyword_query # # Manejo de ubicación/país/remoto - ¡CRUCIAL aquí!
        country_code = None
        province_query = None
        loc_lower = location.lower().strip() if location else ""

        # Intentamos detectar país o remoto
        # Esto es muy básico, necesitaría un mapeo mejor
        if 'ecuador' in loc_lower or 'quito' in loc_lower:
            country_code = 'EC' # if 'quito' in loc_lower:
                 province_query = 'Quito' # O Pichincha? elif 'españa' in loc_lower or 'spain' in loc_lower or 'madrid' in loc_lower or 'barcelona' in loc_lower:
             country_code = 'ES' # if 'madrid' in loc_lower:
                  province_query = 'Madrid'
             elif 'barcelona' in loc_lower:
                  province_query = 'Barcelona'
             # Si es solo 'españa' o 'remote spain', no ponemos provincia?
        # Añadir más países si es necesario (México, Colombia, etc.)

        if any(term in loc_lower for term in ['remote', 'remoto', 'teletrabajo']):
            # ¿Cómo filtra remoto? ¿Parámetro específico? ¿Ubicación especial?
            params['remote'] = '1' # O 'true'? # Quizás si es remoto, no necesita país/provincia? O sí? ¡A investigar!
            # if country_code: params['pais'] = country_code # Mantener país si se detectó?

        elif province_query:
             # ¿Parámetro 'provincia', 'localidad', 'l'?
             params['provincia'] = province_query # # Si hay provincia, ¿también necesita el país?
             if country_code:
                 params['pais'] = country_code # elif country_code:
             # Si solo tenemos país (ej: búsqueda en toda España remoto)
             params['pais'] = country_code # elif location_query:
             # Si no detectamos país/remoto pero hay texto, lo ponemos como ubicación genérica?
             params['l'] = location_query # # Paginación
        if page > 1:
            params['page'] = page # # Creamos la query string.
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()]) if params else ''

        full_url = f"{self.base_url.rstrip('/')}{search_path}"
        if query_string:
            full_url += f"?{query_string}"

        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url

    # Usaremos el _parse_relative_date base si funciona. Adaptar si es necesario.

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Implementación de la búsqueda de trabajos para Empleos.net.
        """
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])
        # La ubicación necesita lógica para país/remoto.
        location = search_params.get('location', 'Quito') # Default a Quito (implica Ecuador).

        while current_page <= MAX_PAGES_TO_SCRAPE_EMPLEOSNET:
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
            job_cards = soup.select('div.offer-item, article.job-card') # if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}. Fin.")
                break

            logger.info(f"[{self.source_name}] {len(job_cards)} ofertas encontradas en página {current_page}.")

            for card in job_cards:
                oferta = self.get_standard_job_dict() # Empezamos estándar.

                # --- Extracción de Datos (Empleos.net) ---
                # ¡Selectores de EJEMPLO! ¡A verificar!

                title_link_element = card.select_one('h2.offer-title a, a.job-link') # oferta['titulo'] = self._safe_get_text(title_link_element)
                detail_or_external_url = self._safe_get_attribute(title_link_element, 'href')

                # Determinamos si la URL es interna (detalle) o externa (aplicar directo)
                is_external_link = False
                if detail_or_external_url:
                     # Construimos URL absoluta por si acaso es relativa
                     absolute_url = urljoin(self.base_url, detail_or_external_url)
                     # Comparamos el dominio base de la URL encontrada con el de empleos.net
                     try:
                         offer_domain = urlparse(absolute_url).netloc
                         base_domain = urlparse(self.base_url).netloc
                         if offer_domain != base_domain:
                             is_external_link = True
                             logger.debug(f"[{self.source_name}] Enlace externo detectado: {absolute_url}")
                     except Exception:
                         logger.warning(f"No se pudo parsear la URL para verificar dominio: {absolute_url}")
                     oferta['url'] = absolute_url # Guardamos la URL (sea interna o externa)
                else:
                     oferta['url'] = None


                company_element = card.select_one('span.company-name, div.company a') # oferta['empresa'] = self._safe_get_text(company_element)

                location_element = card.select_one('span.location, div.location-info') # oferta['ubicacion'] = self._safe_get_text(location_element)

                date_element = card.select_one('span.date, time.published-date') # date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text) # Usar parser base.

                # --- Descripción ---
                oferta['descripcion'] = None # Inicializar.
                if oferta['url'] and not is_external_link:
                    # Si el enlace es INTERNO, intentamos visitar la página de detalle.
                    logger.debug(f"[{self.source_name}] Visitando detalle interno: {oferta['url']}")
                    detail_html = self._fetch_html(oferta['url'])
                    detail_soup = self._parse_html(detail_html)
                    if detail_soup:
                        desc_container = detail_soup.select_one('div.job-description, section.offer-details') # if desc_container:
                             oferta['descripcion'] = self._safe_get_text(desc_container)
                        else:
                             logger.warning(f"[{self.source_name}] No se encontró descripción en detalle interno: {oferta['url']}")
                    else:
                         logger.warning(f"[{self.source_name}] No se pudo parsear detalle interno para: {oferta['url']}")
                elif not is_external_link:
                    # Si no hay URL o es interna pero falló, no hay descripción.
                     logger.warning(f"[{self.source_name}] No URL de detalle válida para: {oferta['titulo']}")
                else:
                    # Si es externa, no tenemos descripción completa. Podríamos tomar un snippet si existe.
                    snippet_element = card.select_one('p.offer-snippet, div.job-summary') # oferta['descripcion'] = self._safe_get_text(snippet_element)
                    if not oferta['descripcion']:
                         logger.debug(f"[{self.source_name}] Enlace externo y no se encontró snippet para: {oferta['titulo']}")


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
                     # Construir URL siguiente (¡cuidado si es relativa o absoluta!)
                     try:
                         current_url = urljoin(current_url, next_page_href) # Unir a la URL actual es más seguro.
                     except Exception:
                          logger.error(f"No se pudo construir URL de paginación desde actual '{current_url}' y relativa '{next_page_href}'")
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

    # Config para Empleos.net (¡Verificar URL!)
    empleosnet_config = {
        'enabled': True,
        'base_url': 'https://www.empleos.net/'
    }

    scraper = EmpleosNetScraper(http_client=http_client, config=empleosnet_config)

    # Búsqueda de ejemplo (Python remoto, intentando filtrar por Ecuador)
    search_params = {
        'keywords': ['python', 'developer'],
        'location': 'Remote Ecuador' # ¿Cómo interpretará esto _build_search_url? Hay que revisar esa lógica.
        # O buscar en Quito: 'location': 'Quito, Ecuador'
    }

    print(f"\n--- Iniciando prueba de EmpleosNetScraper ---")
    print(f"Buscando trabajos con: {search_params}")

    try:
        ofertas = scraper.fetch_jobs(search_params)
        print(f"\n--- Prueba finalizada ---")
        print(f"Se encontraron {len(ofertas)} ofertas.")

        if ofertas:
            print("\nEjemplo de la primera oferta encontrada:")
            pprint.pprint(ofertas[0])
            print("\nNOTA: La 'url' puede ser interna de empleos.net o externa.")
            print("      La 'descripcion' podría ser None o un snippet si la URL es externa.")
        else:
            print("\nNo se encontraron ofertas con los criterios de prueba.")

    except Exception as e:
        logger.exception("Ocurrió un error durante la prueba del scraper EmpleosNet.")
        print(f"\n--- Ocurrió un error durante la prueba: {e} ---")

    finally:
        http_client.close()