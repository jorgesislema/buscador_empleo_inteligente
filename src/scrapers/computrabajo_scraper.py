# -*- coding: utf-8 -*-
# /src/scrapers/computrabajo_scraper.py

"""
Scraper específico para el portal Computrabajo.

Hereda de BaseScraper e implementa la lógica particular
para navegar, extraer y normalizar las ofertas de empleo de este sitio.

¡OJO, COMPAÑERO! Este código depende mucho de la estructura HTML
de Computrabajo. Si ellos cambian su web, estos selectores CSS
probablemente dejarán de funcionar y habrá que actualizarlos.
¡La aventura del scraping! 😄
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import re # Usaremos expresiones regulares para parsear fechas relativas.
from urllib.parse import quote_plus # Para codificar keywords para la URL.

# Importamos nuestra clase base y el cliente HTTP.
from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient

# Obtenemos un logger para este scraper específico.
logger = logging.getLogger(__name__)

# Constante para limitar cuántas páginas revisar por seguridad (evitar bucles infinitos).
MAX_PAGES_TO_SCRAPE = 10 # Podemos ajustar este número.

class ComputrabajoScraper(BaseScraper):
    """
    Implementación del scraper para Computrabajo.

    Se enfoca (inicialmente) en Computrabajo Ecuador (.com.ec).
    """

    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador del scraper de Computrabajo.

        Args:
            http_client (HTTPClient): Instancia del cliente HTTP.
            config (Optional[Dict[str, Any]]): Configuración específica para Computrabajo
                                                desde settings.yaml. Esperamos encontrar 'base_url'.
        """
        # Le pasamos el nombre de la fuente y el cliente HTTP a la clase base.
        super().__init__(source_name="computrabajo", http_client=http_client, config=config)

        # Verificamos que tengamos una URL base en la configuración. ¡Es vital!
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se encontró 'base_url' en la configuración. ¡El scraper no puede funcionar!")
            # Podríamos lanzar un error aquí para detener la carga si es crítico.
            # raise ValueError(f"Configuración para '{self.source_name}' debe incluir 'base_url'.")
            # Por ahora, solo advertimos. fetch_jobs fallará si base_url es None.

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        """
        Construye la URL de búsqueda para Computrabajo Ecuador.

        Args:
            keywords (List[str]): Lista de palabras clave.
            location (str): La ubicación principal de búsqueda (ej: "Quito", "Remote Ecuador").
            page (int): El número de página de resultados a solicitar.

        Returns:
            Optional[str]: La URL construida o None si falta la URL base.
        """
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL de búsqueda sin 'base_url'.")
            return None

        # Unimos las keywords con '+' o '%20' para la URL. Usaremos quote_plus para seguridad.
        # Ejemplo: ['data', 'analyst'] -> 'data+analyst'
        keyword_query = quote_plus(' '.join(keywords)) if keywords else ''

        # --- Lógica para la ubicación (¡Esto puede necesitar ajustes!) ---
        # Computrabajo EC usa provincias y a veces ciudades en parámetros.
        # Necesitamos mapear nuestra 'location' a lo que espera Computrabajo.
        # Asumiremos un mapeo simple por ahora. ¡VERIFICAR ESTO!
        location_query = ''
        if location and location.lower() == 'quito':
             # Para Quito, usualmente se busca por provincia 'Pichincha'. ID 17?
             # Ejemplo (puede variar): &prov=17 o &p=Pichincha
             location_query = "&p=Pichincha" # elif location and 'remote' in location.lower():
            # ¿Cómo busca remoto Computrabajo? ¿Un filtro? ¿Palabra clave?
            # Añadamos 'remoto' a las keywords si no está ya.
            if 'remoto' not in keyword_query.lower() and 'trabajo remoto' not in keyword_query.lower():
                 keyword_query += '+remoto'
            # Quizás no haya parámetro de ubicación específico para remoto.
            location_query = "" # Dejar vacío para buscar en todo el país (o donde aplique remoto).
        # Podríamos añadir más mapeos para otras ubicaciones si expandimos el scope.

        # Construimos la URL final. La estructura puede cambiar.
        # Ejemplo: https://www.computrabajo.com.ec/ofertas-de-trabajo/?q=data+scientist&p=Pichincha&p=1
        # ¡VERIFICAR LA ESTRUCTURA URL REAL!
        search_url = f"{self.base_url}/ofertas-de-trabajo/?q={keyword_query}{location_query}" # # Añadimos el parámetro de paginación (suele ser 'p' o 'page').
        # ¡VERIFICAR NOMBRE DEL PARÁMETRO DE PÁGINA!
        if page > 1:
            search_url += f"&pg={page}" # logger.debug(f"[{self.source_name}] URL de búsqueda construida: {search_url}")
        return search_url

    def _parse_relative_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Intenta convertir fechas relativas ("Hoy", "Ayer", "Hace N días") a formato YYYY-MM-DD.

        Args:
            date_str (Optional[str]): El texto de la fecha extraído de la página.

        Returns:
            Optional[str]: La fecha en formato YYYY-MM-DD o el texto original si no se pudo parsear.
        """
        if not date_str:
            return None

        date_str_lower = date_str.lower().strip()
        today = datetime.now().date()

        if 'hoy' in date_str_lower:
            return today.strftime('%Y-%m-%d')
        elif 'ayer' in date_str_lower:
            yesterday = today - timedelta(days=1)
            return yesterday.strftime('%Y-%m-%d')
        elif 'hace' in date_str_lower:
            # Buscamos números en el string con expresión regular.
            match = re.search(r'hace\s+(\d+)\s+días?', date_str_lower)
            if match:
                try:
                    days_ago = int(match.group(1))
                    past_date = today - timedelta(days=days_ago)
                    return past_date.strftime('%Y-%m-%d')
                except ValueError:
                    logger.warning(f"[{self.source_name}] No se pudo convertir a número los días en: '{date_str}'")
                    return date_str # Devolver original si falla la conversión
            else:
                # No coincide con "hace N días", puede ser otra cosa.
                return date_str # Devolver original
        else:
            # Si no es relativa conocida, intentamos parsearla como fecha normal
            # o simplemente devolvemos el texto original.
            # Podríamos añadir más lógica de parseo si Computrabajo usa formatos fijos.
            return date_str # Devolver original por defecto.


    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Implementación de la búsqueda de trabajos para Computrabajo.
        """
        logger.info(f"[{self.source_name}] Iniciando búsqueda de trabajos con parámetros: {search_params}")
        all_job_offers = []
        current_page = 1

        # Sacamos las keywords y la ubicación principal de los parámetros.
        # Asumimos que vienen en una lista, las unimos. Puede necesitar ajustes.
        keywords = search_params.get('keywords', [])
        # Por ahora, tomamos la primera ubicación relevante de la lista.
        # Necesitaríamos lógica más robusta si buscamos en varias a la vez.
        location = search_params.get('location', 'Quito') # Default a Quito si no se especifica

        while current_page <= MAX_PAGES_TO_SCRAPE:
            logger.info(f"[{self.source_name}] Procesando página {current_page}...")

            # Construimos la URL para la página actual.
            current_url = self._build_search_url(keywords, location, current_page)
            if not current_url:
                logger.error(f"[{self.source_name}] No se pudo construir la URL para la página {current_page}. Abortando.")
                break # Salir si no podemos ni construir la URL.

            # Descargamos el HTML de la página de listado.
            html_content = self._fetch_html(current_url)
            if not html_content:
                logger.warning(f"[{self.source_name}] No se pudo obtener HTML de la página {current_page}. Terminando paginación.")
                break # Salir si no hay HTML.

            # Parseamos el HTML.
            soup = self._parse_html(html_content)
            if not soup:
                logger.warning(f"[{self.source_name}] No se pudo parsear HTML de la página {current_page}. Terminando paginación.")
                break # Salir si no podemos parsear.

            # ¡La parte crucial! Encontrar los contenedores de cada oferta.
            # Necesitamos inspeccionar Computrabajo.com.ec y encontrar el selector CSS correcto.
            # Este selector es SOLO UN EJEMPLO y casi seguro habrá que cambiarlo.
            job_cards = soup.select('article.box_offer') # if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron ofertas en la página {current_page}. Parece que es la última página.")
                break # No hay más ofertas, terminamos.

            logger.info(f"[{self.source_name}] Encontradas {len(job_cards)} ofertas en la página {current_page}.")

            # Procesamos cada tarjeta de oferta encontrada.
            for card in job_cards:
                oferta = self.get_standard_job_dict() # Empezamos con nuestro diccionario estándar.

                # --- Extracción de Datos de la Tarjeta ---
                # De nuevo, estos selectores son EJEMPLOS. ¡Hay que verificarlos!

                # Título y URL de Detalle (suelen estar en el mismo enlace)
                title_link_element = card.select_one('h1.js-o-link a, p.title a') # oferta['titulo'] = self._safe_get_text(title_link_element)
                detail_url_relative = self._safe_get_attribute(title_link_element, 'href')
                # Construimos la URL absoluta si es relativa.
                oferta['url'] = self._build_url(detail_url_relative) if detail_url_relative else None

                # Empresa
                company_element = card.select_one('div.fs16 a, span.d-block a') # oferta['empresa'] = self._safe_get_text(company_element)

                # Ubicación (puede tener ciudad y provincia)
                location_element = card.select_one('p span:not([class]), span span[title]') # oferta['ubicacion'] = self._safe_get_text(location_element)

                # Fecha de Publicación (suele ser relativa)
                date_element = card.select_one('span.fc_aux, p.fs13 span') # date_text = self._safe_get_text(date_element)
                oferta['fecha_publicacion'] = self._parse_relative_date(date_text) # Usamos nuestro parser!

                # --- Visitar Página de Detalle (Opcional pero recomendado para descripción) ---
                if oferta['url']:
                    logger.debug(f"[{self.source_name}] Visitando página de detalle: {oferta['url']}")
                    detail_html = self._fetch_html(oferta['url'])
                    detail_soup = self._parse_html(detail_html)
                    if detail_soup:
                        # Extraer Descripción
                        # ¡Selector de ejemplo! Hay que buscar el contenedor de la descripción.
                        desc_element = detail_soup.select_one('section#description>div>p, div.fs16') # oferta['descripcion'] = self._safe_get_text(desc_element)
                        # Podríamos buscar más detalles aquí (salario, tipo contrato, etc.)
                    else:
                        logger.warning(f"[{self.source_name}] No se pudo parsear la página de detalle para: {oferta['url']}")
                else:
                     logger.warning(f"[{self.source_name}] No se encontró URL de detalle para la oferta: {oferta['titulo']}")


                # Añadimos la oferta a nuestra lista si tenemos lo mínimo (título y URL).
                if oferta['titulo'] and oferta['url']:
                    all_job_offers.append(oferta)
                else:
                    logger.warning(f"[{self.source_name}] Oferta omitida por faltar título o URL.")


            # --- Lógica de Paginación ---
            # Buscamos el enlace a la página siguiente. ¡Selector de ejemplo!
            next_page_link = soup.select_one('a.arrow_pag > span.icon-right-arrow') # # Otra forma podría ser buscar li.active + li > a

            if next_page_link:
                # Si encontramos el botón/enlace, incrementamos la página.
                # La URL se reconstruirá al inicio del bucle while.
                current_page += 1
                logger.debug(f"[{self.source_name}] Enlace a página siguiente encontrado. Pasando a página {current_page}.")
            else:
                # Si no hay enlace 'Siguiente', asumimos que es la última página.
                logger.info(f"[{self.source_name}] No se encontró enlace a página siguiente en la página {current_page-1}. Terminando paginación.")
                break # Salimos del bucle while.

        # Fin del bucle while (paginación)

        logger.info(f"[{self.source_name}] Búsqueda finalizada. Se encontraron {len(all_job_offers)} ofertas en total.")
        return all_job_offers

# --- Ejemplo de uso (si ejecutamos este script directamente) ---
if __name__ == '__main__':
    # Necesitamos configurar logging y http_client para probar.
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient

    # Configuramos logging básico para ver los mensajes.
    setup_logging() # Usará la config de settings.yaml si existe y es correcta.

    # Creamos el cliente HTTP.
    http_client = HTTPClient()

    # Simulamos la configuración que vendría de settings.yaml para Computrabajo.
    # ¡Asegúrate de poner la URL base correcta para Ecuador!
    computrabajo_config = {
        'enabled': True,
        'base_url': 'https://www.computrabajo.com.ec' # ¡URL para Ecuador!
    }

    # Creamos una instancia de nuestro scraper.
    scraper = ComputrabajoScraper(http_client=http_client, config=computrabajo_config)

    # Definimos parámetros de búsqueda de ejemplo.
    search_params = {
        'keywords': ['analista', 'datos'],
        'location': 'Quito' # O podría ser 'Remote Ecuador'
    }

    print(f"\n--- Iniciando prueba de ComputrabajoScraper ---")
    print(f"Buscando trabajos con: {search_params}")

    # Llamamos al método principal.
    try:
        ofertas = scraper.fetch_jobs(search_params)
        print(f"\n--- Prueba finalizada ---")
        print(f"Se encontraron {len(ofertas)} ofertas.")

        # Imprimimos la primera oferta encontrada (si existe) para verla.
        if ofertas:
            print("\nEjemplo de la primera oferta encontrada:")
            # Usamos pprint para que el diccionario se vea más bonito.
            import pprint
            pprint.pprint(ofertas[0])
        else:
            print("\nNo se encontraron ofertas con los criterios de prueba.")

    except Exception as e:
        logger.exception("Ocurrió un error durante la prueba del scraper.")
        print(f"\n--- Ocurrió un error durante la prueba: {e} ---")

    finally:
        # Cerramos el cliente HTTP al final.
        http_client.close()