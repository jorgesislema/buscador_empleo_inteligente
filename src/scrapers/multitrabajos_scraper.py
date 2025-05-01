# -*- coding: utf-8 -*-
# /src/scrapers/multitrabajos_scraper.py

"""
Scraper específico para el portal Multitrabajos (Ecuador).

Hereda de BaseScraper y define la lógica para extraer ofertas
de multitrabajos.com.

Compañero, ¡ya sabes el trato! Revisa y ajusta los selectores CSS
y la lógica de construcción de URLs según la estructura actual de la web.
¡A ponerse el sombrero de detective HTML! 🕵️‍♀️
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta # Para fechas relativas
import re # Para parsear fechas si es necesario
from urllib.parse import quote, unquote # Para manejar URLs y keywords

# Importamos lo necesario de nuestra base y utilidades
from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

# Logger para este scraper
logger = logging.getLogger(__name__)

# Límite de páginas para no excedernos
MAX_PAGES_TO_SCRAPE_MULTITRABAJOS = 10 # Ajustar si es necesario

class MultitrabajosScraper(BaseScraper):
    """
    Implementación del scraper para Multitrabajos.com.
    """

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador del scraper de Multitrabajos.

        Args:
            http_client (HTTPClient): Instancia del cliente HTTP.
            config (Optional[Dict[str, Any]]): Config específica (esperamos 'base_url').
        """
        super().__init__(source_name="multitrabajos", http_client=http_client, config=config)

        if not self.base_url or 'multitrabajos.com' not in self.base_url:
            logger.error(f"[{self.source_name}] 'base_url' inválida o no encontrada para Multitrabajos.")
            # Podríamos intentar un default, pero es mejor que esté en la config.
            self.base_url = "https://www.multitrabajos.com" # Default tentativo
            logger.warning(f"Usando URL base por defecto: {self.base_url}")

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        """
        Construye la URL de búsqueda para Multitrabajos.com.

        Parece usar una estructura de path como: /empleos-busqueda-[keywords]-en-[localizacion].html?page=[N]
        ¡Necesita verificación!

        Args:
            keywords (List[str]): Lista de palabras clave.
            location (str): La ubicación (ej: "Quito", "Remote Ecuador").
            page (int): El número de página.

        Returns:
            Optional[str]: La URL construida o None si falta la URL base.
        """
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        # Limpiamos y unimos keywords, reemplazando espacios con '-' (común en paths URL).
        keyword_slug = '-'.join(k.strip() for k in keywords if k.strip()).lower()
        # Codificamos por si acaso hay caracteres especiales, aunque el path suele ser más simple.
        keyword_slug = quote(keyword_slug)

        # --- Lógica de Ubicación para Multitrabajos ---
        # ¡Suposiciones aquí! Verificar cómo maneja la web las ubicaciones y remoto.
        location_slug = ""
        loc_lower = location.lower().strip() if location else ""

        if any(term in loc_lower for term in ['remote', 'remoto', 'teletrabajo']):
            # ¿Cómo indica remoto? ¿Quizás añadiendo '-remoto' a keywords o un path específico?
            # Opción 1: Añadir a keywords
            if 'remoto' not in keyword_slug:
                keyword_slug = f"{keyword_slug}-remoto" if keyword_slug else "remoto"
            # Opción 2: ¿Quizás no necesita localización si es remoto? Dejamos el slug vacío.
            location_slug = "" # elif loc_lower == 'quito':
            # Mapeo específico para Quito (o Pichincha?)
            location_slug = "quito" # O podría ser "pichincha"? elif loc_lower:
            # Para otras ubicaciones, usamos el nombre en minúsculas y con guiones.
            location_slug = quote(loc_lower.replace(" ", "-"))

        # Construimos el path. ¡Esta estructura es una suposición!
        # Formato: /empleos-busqueda-[keywords]-en-[localizacion].html
        if keyword_slug and location_slug:
             path = f"/empleos-busqueda-{keyword_slug}-en-{location_slug}.html"
        elif keyword_slug:
             path = f"/empleos-busqueda-{keyword_slug}.html"
        elif location_slug: # ¿Búsqueda solo por ubicación?
             path = f"/empleos-en-{location_slug}.html" # else:
             path = "/empleos.html" # O la URL base de empleos # Añadimos la paginación (si aplica y cómo aplica).
        # ¿Es un parámetro ?page=N o parte de la ruta? Asumamos parámetro.
        page_param = f"?page={page}" if page > 1 else "" # full_url = f"{self.base_url.rstrip('/')}{path}{page_param}"
        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {full_url}")
        return full_url

    def _parse_relative_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Sobreescribimos o extendemos el parser base si Multitrabajos usa formatos específicos.
        (Podríamos reutilizar el de BaseScraper si maneja "Publicado hoy/ayer/hace...")
        """
        if not date_str:
            return None
        # Añadimos lógica para "Publicado hoy", "Publicado ayer", etc.
        date_str_lower = date_str.lower().strip()
        today = datetime.now().date()

        if 'publicado hoy' in date_str_lower:
            return today.strftime('%Y-%m-%d')
        elif 'publicado ayer' in date_str_lower:
            yesterday = today - timedelta(days=1)
            return yesterday.strftime('%Y-%m-%d')
        elif 'publicado hace' in date_str_lower:
            match = re.search(r'hace\s+(\d+)\s+días?', date_str_lower)
            if match:
                try:
                    days_ago = int(match.group(1))
                    past_date = today - timedelta(days=days_ago)
                    return past_date.strftime('%Y-%m-%d')
                except ValueError:
                     logger.warning(f"[{self.source_name}] No se pudo convertir días en: '{date_str}'")
                     return date_str
            else:
                return date_str # Devolver original si no coincide el patrón
        else:
            # Si no es ninguno de los anteriores, usamos el parser de la clase base (si existe y es útil)
            # o simplemente devolvemos el original.
            # return super()._parse_relative_date(date_str) # Si el base tuviera más lógica
            return date_str # Devolver original por ahora.

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Implementación de la búsqueda de trabajos para Multitrabajos.
        """
        logger.info(f"[{self.source_name}] Iniciando búsqueda con: {search_params}")
        all_job_offers = []
        current_page = 1
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', 'Quito') # Default a Quito

        while current_page <= MAX_PAGES_TO_SCRAPE_MULTITRABAJOS:
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

            # Encontrar tarjetas de ofertas. ¡Selector de EJEMPLO!
            # Puede ser 'article' o 'div' con una clase específica.
            job_cards = soup.select('div.aviso-container, article[data-id-aviso]') # if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en página {current_page}. Fin.")
                break

            logger.info(f"[{self.source_name}] {len(job_cards)} ofertas encontradas en página {current_page}.")

            for card in job_cards:
                oferta = self.get_standard_job_dict() # Empezamos estándar.

                # --- Extracción de Datos de la Tarjeta (Multitrabajos) ---
                # ¡Selectores de EJEMPLO! ¡A verificar!

                title_link_element = card.select_one('h2 a, a.titulo-aviso') # oferta['titulo'] = self._safe_get_text(title_link_element)
                detail_url_relative = self._safe_get_attribute(title_link_element, 'href')
                oferta['url'] = self._build_url(detail_url_relative) # Construir URL absoluta.

                company_element = card.select_one('h3[data-company-name], span.nombre-empresa') # oferta['empresa'] = self._safe_get_text(company_element)
                # A veces el nombre está en un atributo 'data-company-name' o similar.
                if not oferta['empresa'] and company_element:
                     oferta['empresa'] = company_element.get('data-company-name')

                location_element = card.select_one('span.location-text, div.ubicacion span') # oferta['ubicacion'] = self._safe_get_text(location_element)

                date_element = card.select_one('h4.fecha, span.fecha-publicacion') # date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text) # Usar nuestro parser.

                # --- Visitar Página de Detalle para Descripción ---
                oferta['descripcion'] = None # Inicializar por si falla la visita al detalle.
                if oferta['url']:
                    logger.debug(f"[{self.source_name}] Visitando detalle: {oferta['url']}")
                    detail_html = self._fetch_html(oferta['url']) # Podríamos añadir un delay extra aquí si queremos.
                    detail_soup = self._parse_html(detail_html)
                    if detail_soup:
                        # Buscar el contenedor de la descripción. ¡Selector de EJEMPLO!
                        desc_container = detail_soup.select_one('div.aviso_description, section.detalle-aviso') # # A veces la descripción está repartida en varios párrafos <p> dentro del contenedor.
                        if desc_container:
                             # Unimos el texto de todos los párrafos o tomamos el texto del contenedor.
                             paragraphs = desc_container.find_all('p')
                             if paragraphs:
                                 oferta['descripcion'] = "\n".join([self._safe_get_text(p) for p in paragraphs if self._safe_get_text(p)])
                             else:
                                 # Si no hay <p>, tomamos el texto del contenedor principal.
                                 oferta['descripcion'] = self._safe_get_text(desc_container)
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
            # Puede ser un 'a' con clase 'next', un 'li' con clase 'next', etc.
            next_page_link_element = soup.select_one('a.nav-pag-arrow-right, li.next a') # if next_page_link_element:
                next_page_href = self._safe_get_attribute(next_page_link_element, 'href')
                if next_page_href and next_page_href != '#':
                    # Construir URL siguiente. Podría ser relativa.
                    current_url = self._build_url(next_page_href) # Usamos el helper.
                    current_page += 1 # Avanzamos nuestro contador de página.
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

    # Config para Multitrabajos Ecuador
    multitrabajos_config = {
        'enabled': True,
        'base_url': 'https://www.multitrabajos.com'
    }

    scraper = MultitrabajosScraper(http_client=http_client, config=multitrabajos_config)

    # Búsqueda de ejemplo
    search_params = {
        'keywords': ['datos'],
        'location': 'Quito'
    }

    print(f"\n--- Iniciando prueba de MultitrabajosScraper ---")
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
        logger.exception("Ocurrió un error durante la prueba del scraper Multitrabajos.")
        print(f"\n--- Ocurrió un error durante la prueba: {e} ---")

    finally:
        http_client.close()