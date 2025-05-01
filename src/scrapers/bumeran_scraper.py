# -*- coding: utf-8 -*-
# /src/scrapers/bumeran_scraper.py

"""
Scraper específico para el portal Bumeran (enfocado en Ecuador).

Hereda de BaseScraper y contiene la lógica para extraer ofertas de
bumeran.com.ec (o el dominio correspondiente).

Compañero, ya te la sabes: ¡a revisar bumeran.com.ec con F12 y ajustar
selectores y URLs! Cada portal es un pequeño mundo HTML por descubrir.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta # Para fechas
import re # Por si acaso
from urllib.parse import quote_plus, quote, urljoin # Para URLs

# Nuestras herramientas base
from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

# Logger para este scraper
logger = logging.getLogger(__name__)

# Límite de páginas
MAX_PAGES_TO_SCRAPE_BUMERAN = 10 # Ajustable

class BumeranScraper(BaseScraper):
    """
    Implementación del scraper para Bumeran (versión Ecuador).
    """

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador del scraper de Bumeran.

        Args:
            http_client (HTTPClient): Instancia del cliente HTTP.
            config (Optional[Dict[str, Any]]): Config específica (esperamos 'base_url').
        """
        super().__init__(source_name="bumeran", http_client=http_client, config=config)

        # URL base por defecto si no está en la config. ¡Verificarla para Ecuador!
        if not self.base_url:
            self.base_url = "https://www.bumeran.com.ec/" # logger.warning(f"[{self.source_name}] 'base_url' no encontrada en config. Usando default: {self.base_url}")

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        """
        Construye la URL de búsqueda para Bumeran.

        Puede usar una estructura de path como /empleos-busqueda-[kw]-localidad-[loc]-pagina-[p].html
        ¡Necesita verificación!

        Args:
            keywords (List[str]): Palabras clave.
            location (str): Ubicación (ej: "Quito", "Pichincha", "Remoto").
            page (int): Número de página (OJO: Bumeran a veces usa página 0 o 1 como inicio).

        Returns:
            Optional[str]: La URL construida o None.
        """
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        # Unimos keywords con '-'.
        keyword_slug = '-'.join(quote(k.strip()) for k in keywords if k.strip()).lower()

        # --- Lógica de Ubicación/Remoto Bumeran ---
        # ¡Suposiciones aquí!
        location_slug = ""
        loc_lower = location.lower().strip() if location else ""

        if any(term in loc_lower for term in ['remote', 'remoto', 'teletrabajo']):
            # ¿Cómo busca remoto Bumeran? ¿Palabra clave? ¿Ubicación especial?
            # Opción: añadir 'remoto' a keywords si no está.
            if 'remoto' not in keyword_slug:
                keyword_slug = f"{keyword_slug}-remoto" if keyword_slug else "remoto"
            # Dejar location_slug vacío para buscar en todo el país?
            location_slug = "" # elif loc_lower == 'quito':
            location_slug = "quito-pichincha" # O solo 'pichincha'? elif loc_lower == 'pichincha':
            location_slug = 'pichincha'
        elif loc_lower:
            # Para otras, usamos el nombre simple codificado.
            location_slug = quote(loc_lower.replace(" ", "-"))

        # Construimos el path. ¡Estructura basada en ejemplos pasados, PUEDE CAMBIAR!
        # Formato posible: /empleos-busqueda-[kw]-localidad-[loc]-pagina-[p].html
        path = "/empleos" # Path base if keyword_slug:
            path += f"-busqueda-{keyword_slug}"
        if location_slug:
            # ¿Usa '-en-' o '-localidad-'?
            path += f"-localidad-{location_slug}" # # Paginación: ¿'-pagina-N'? ¿O parámetro? ¿Empieza en 0 o 1?
        # Asumamos formato en path y que empieza en 1 (page=1 no lleva sufijo).
        if page > 1:
            path += f"-pagina-{page}" # path += ".html" # ¿Termina en .html? full_url = f"{self.base_url.rstrip('/')}{path}"
        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url

    # Usaremos el _parse_relative_date base si funciona (para "hace N días"). Adaptar si es necesario.

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Implementación de la búsqueda de trabajos para Bumeran Ecuador.
        """
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_job_offers = []
        # Bumeran podría empezar paginación en 0 o 1, probemos con 1. ¡VERIFICAR!
        current_page = 1 # keywords = search_params.get('keywords', [])
        location = search_params.get('location', 'Quito') # Default

        while current_page <= MAX_PAGES_TO_SCRAPE_BUMERAN:
            logger.info(f"[{self.source_name}] Procesando página {current_page}...")

            current_url = self._build_search_url(keywords, location, current_page)
            if not current_url:
                logger.error(f"[{self.source_name}] URL inválida para página {current_page}. Abortando.")
                break

            html_content = self._fetch_html(current_url)
            if not html_content:
                # Si falla al buscar la página 1, puede ser error de URL. Si falla más tarde, puede ser fin paginación.
                if current_page == 1:
                     logger.error(f"[{self.source_name}] No se obtuvo HTML de la PRIMERA página. ¿URL de búsqueda correcta?")
                else:
                     logger.warning(f"[{self.source_name}] No se obtuvo HTML de página {current_page}. Asumiendo fin de paginación.")
                break

            soup = self._parse_html(html_content)
            if not soup:
                logger.warning(f"[{self.source_name}] No se parseó HTML de página {current_page}. Terminando.")
                break

            # Encontrar las ofertas. ¡Selector de EJEMPLO! Similar a Multitrabajos?
            job_cards = soup.select('div.aviso-container, div#listado-avisos > div') # if not job_cards:
                # A veces la página carga pero sin resultados (puede ser la última página real)
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}. Fin.")
                break

            logger.info(f"[{self.source_name}] {len(job_cards)} ofertas encontradas en página {current_page}.")

            for card in job_cards:
                oferta = self.get_standard_job_dict() # Empezamos estándar.

                # --- Extracción de Datos (Bumeran) ---
                # ¡Selectores de EJEMPLO! ¡A verificar!

                title_link_element = card.select_one('a.titulo-aviso, h2.job-title a') # oferta['titulo'] = self._safe_get_text(title_link_element)
                detail_url_relative = self._safe_get_attribute(title_link_element, 'href')
                oferta['url'] = self._build_url(detail_url_relative) # Construir URL absoluta.

                company_element = card.select_one('a.empresa-nombre, h3.job-company') # oferta['empresa'] = self._safe_get_text(company_element)

                location_element = card.select_one('span.detalle-aviso-location, div.job-location') # oferta['ubicacion'] = self._safe_get_text(location_element)

                date_element = card.select_one('h4.fecha, span.job-date') # date_text = self._safe_get_text(date_element)
                # Usar parser relativo base (para "hace N días").
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text)

                # --- Visitar Página de Detalle ---
                oferta['descripcion'] = None # Inicializar.
                if oferta['url']:
                    logger.debug(f"[{self.source_name}] Visitando detalle: {oferta['url']}")
                    detail_html = self._fetch_html(oferta['url'])
                    detail_soup = self._parse_html(detail_html)
                    if detail_soup:
                        # Buscar descripción. ¡Selector de EJEMPLO!
                        desc_container = detail_soup.select_one('div.aviso_description, div.job-description-detail') # if desc_container:
                             oferta['descripcion'] = self._safe_get_text(desc_container)
                        else:
                             logger.warning(f"[{self.source_name}] No se encontró descripción en: {oferta['url']}")
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
            # ¿Cómo sabemos si hay página siguiente? ¿Buscando el enlace/botón "Siguiente"?
            # O quizás comprobando si un botón de página está deshabilitado. ¡A investigar!
            next_page_link_element = soup.select_one('a.nav-pag-arrow-right:not(.disabled), li.next:not(.disabled) a') # if next_page_link_element:
                 # Si encontramos un enlace "siguiente" activo, simplemente incrementamos la página.
                 # La URL se reconstruirá al inicio del bucle.
                 current_page += 1
                 logger.debug(f"[{self.source_name}] Posible página siguiente encontrada. Intentando página {current_page}.")
            else:
                 logger.info(f"[{self.source_name}] No se encontró enlace 'Siguiente' activo. Fin.")
                 break # Salimos del bucle while.

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

    # Config para Bumeran Ecuador (¡Verificar URL!)
    bumeran_config = {
        'enabled': True,
        'base_url': 'https://www.bumeran.com.ec/'
    }

    scraper = BumeranScraper(http_client=http_client, config=bumeran_config)

    # Búsqueda de ejemplo
    search_params = {
        'keywords': ['supervisor'],
        'location': 'Quito'
    }

    print(f"\n--- Iniciando prueba de BumeranScraper ---")
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
        logger.exception("Ocurrió un error durante la prueba del scraper Bumeran.")
        print(f"\n--- Ocurrió un error durante la prueba: {e} ---")

    finally:
        http_client.close()