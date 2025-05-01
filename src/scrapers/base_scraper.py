# -*- coding: utf-8 -*-
# /src/scrapers/base_scraper.py

"""
Plantilla Base para los Scrapers de Sitios Web de Empleo.

Aquí definimos la estructura y herramientas comunes para todos nuestros
scrapers (Computrabajo, Infojobs, etc.). Usamos una Clase Base Abstracta (ABC)
para asegurar que todos implementen la funcionalidad esencial.

El scraping puede ser frágil porque las páginas web cambian. Tener una
base sólida con helpers nos ayudará a mantener el código más limpio y
fácil de actualizar cuando un sitio cambie su diseño. ¡Ánimo, equipo!
"""

import abc          # Para la Clase Base Abstracta.
import logging      # Para nuestro "diario de a bordo".
from typing import List, Dict, Any, Optional # Type hints para claridad.
# Necesitamos BeautifulSoup para parsear HTML. ¡Asegúrate de tenerla instalada! (viene con beautifulsoup4)
from bs4 import BeautifulSoup, Tag # Tag es el tipo para un elemento HTML en BeautifulSoup.

# Importamos nuestro cliente HTTP y el tipo Response por si lo necesitamos.
from src.utils.http_client import HTTPClient
from requests import Response # Usamos el tipo Response para type hinting.

# Obtenemos un logger para este módulo base.
logger = logging.getLogger(__name__)

class BaseScraper(abc.ABC):
    """
    Clase Base Abstracta para todos los scrapers de sitios de empleo.

    Define la interfaz común y provee métodos de ayuda para tareas
    repetitivas como descargar y parsear HTML de forma segura.

    Atributos:
        source_name (str): Nombre identificador de la fuente (ej: 'computrabajo').
        http_client (HTTPClient): Instancia del cliente HTTP para descargar páginas.
        config (dict): Configuración específica de la fuente leída de settings.yaml.
    """

    def __init__(self, source_name: str, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializador de la clase base del scraper.

        Args:
            source_name (str): El nombre único de esta fuente web (ej: "computrabajo").
                               Debería coincidir con la clave en settings.yaml -> sources -> scrapers.
            http_client (HTTPClient): Una instancia ya inicializada de nuestro cliente HTTP.
            config (Optional[Dict[str, Any]]): Config específica para este scraper desde settings.yaml
                                                (ej: {'enabled': True, 'base_url': 'https://...'}). Defaults to None.
        """
        self.source_name = source_name
        self.http_client = http_client
        self.config = config if config is not None else {}
        logger.info(f"Inicializando scraper base para la fuente: '{self.source_name}'")
        if not isinstance(http_client, HTTPClient):
             logger.error("¡Se esperaba una instancia de HTTPClient pero se recibió algo diferente!")
             raise TypeError("El argumento http_client debe ser una instancia de HTTPClient.")
        # Podríamos sacar la URL base de la config aquí si siempre la necesitamos.
        self.base_url = self.config.get('base_url', None)
        if not self.base_url:
            logger.warning(f"No se encontró 'base_url' en la configuración para '{self.source_name}'. "
                           "La clase hija deberá manejar la construcción de URLs.")


    @abc.abstractmethod
    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Método abstracto principal para obtener ofertas de empleo del sitio web.

        **¡Cada scraper específico DEBE implementar este método!**

        Debe encargarse de:
        1. Construir la(s) URL(s) de búsqueda o listado del sitio web.
        2. Navegar por las páginas de resultados (manejar paginación).
        3. Para cada oferta (o en cada página de listado):
            a. Descargar el HTML necesario usando `_fetch_html`.
            b. Parsear el HTML usando `_parse_html`.
            c. Extraer los datos relevantes de cada oferta (título, empresa, etc.).
               Esto puede implicar visitar páginas de detalle de cada oferta.
            d. **Normalizar** los datos al formato estándar.
        4. Devolver una lista de diccionarios con claves estándar. Devolver
           lista vacía si no hay resultados o hay error.

        Args:
            search_params (Dict[str, Any]): Parámetros de búsqueda (keywords, location).
                                           La forma de usarlos dependerá de cómo funcione
                                           la búsqueda en cada sitio web específico.

        Returns:
            List[Dict[str, Any]]: Lista de diccionarios de ofertas con claves estándar
                                  ('titulo', 'empresa', 'ubicacion', 'descripcion',
                                  'fecha_publicacion', 'url', 'fuente').
        """
        raise NotImplementedError("¡Oops! La clase scraper hija olvidó implementar fetch_jobs.")


    # --- Métodos de Ayuda para las Clases Hijas ---

    def _fetch_html(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[str]:
        """
        Descarga el contenido HTML de una URL usando nuestro HTTPClient.

        Args:
            url (str): La URL de la página a descargar.
            params (Optional[Dict], optional): Parámetros GET para la URL. Defaults to None.
            headers (Optional[Dict], optional): Cabeceras extra para la petición. Defaults to None.

        Returns:
            Optional[str]: El contenido HTML de la página como texto, o None si falla la descarga.
        """
        logger.debug(f"[{self.source_name}] Intentando descargar HTML de: {url}")
        response = self.http_client.get(url, params=params, headers=headers)

        # Verificamos si nuestro cliente HTTP nos devolvió una respuesta válida.
        if response and response.status_code == 200:
            # ¡Genial! Tenemos la respuesta. Devolvemos el contenido HTML.
            # response.text decodifica el contenido (usualmente bien, pero a veces
            # hay que revisar response.encoding si hay caracteres raros).
            logger.debug(f"[{self.source_name}] HTML descargado exitosamente de: {url}")
            return response.text
        elif response:
            # La petición se hizo, pero el servidor respondió con error (4xx, 5xx)
            # Nuestro http_client ya habrá logueado el error.
            logger.warning(f"[{self.source_name}] Se recibió código de estado {response.status_code} al intentar descargar {url}")
            return None
        else:
            # La petición falló por completo (timeout, error de conexión, etc.)
            # Nuestro http_client ya habrá logueado el error.
            logger.error(f"[{self.source_name}] Falló la descarga de HTML de {url} (http_client devolvió None).")
            return None

    def _parse_html(self, html_content: Optional[str]) -> Optional[BeautifulSoup]:
        """
        Parsea una cadena de texto HTML usando BeautifulSoup.

        Args:
            html_content (Optional[str]): El contenido HTML a parsear.

        Returns:
            Optional[BeautifulSoup]: Un objeto BeautifulSoup listo para buscar elementos,
                                     o None si el contenido HTML es inválido o vacío.
        """
        if not html_content:
            logger.debug(f"[{self.source_name}] No hay contenido HTML para parsear.")
            return None

        try:
            # Aquí usamos BeautifulSoup para convertir el texto HTML en un objeto
            # que podemos navegar y buscar fácilmente. Usamos 'lxml' como parser
            # porque es rápido y robusto. ¡Asegúrate de tenerlo instalado!
            # (pip install lxml) -> Ya debería estar en requirements.txt
            soup = BeautifulSoup(html_content, 'lxml')
            return soup
        except Exception as e:
            # Capturamos errores que podrían ocurrir durante el parseo si el HTML está muy mal formado.
            logger.error(f"[{self.source_name}] Error al parsear HTML con BeautifulSoup: {e}", exc_info=True)
            return None

    def _safe_get_text(self, soup_element: Optional[Tag]) -> Optional[str]:
        """
        Obtiene el texto de un elemento de BeautifulSoup de forma segura.

        Si el elemento existe, devuelve su texto limpio (sin espacios extra al inicio/final).
        Si el elemento es None (porque no se encontró), devuelve None sin dar error.
        ¡Esto nos ahorra muchos 'if element:' checks en el código del scraper!

        Args:
            soup_element (Optional[Tag]): El elemento BeautifulSoup (o None).

        Returns:
            Optional[str]: El texto limpio del elemento, o None.
        """
        if soup_element:
            # .get_text() obtiene todo el texto dentro de la etiqueta.
            # strip=True elimina espacios/saltos de línea molestos al principio y al final.
            return soup_element.get_text(strip=True)
        else:
            return None

    def _safe_get_attribute(self, soup_element: Optional[Tag], attribute: str) -> Optional[str]:
        """
        Obtiene el valor de un atributo de un elemento BeautifulSoup de forma segura.

        Similar a _safe_get_text, pero para atributos (ej: el 'href' de un enlace <a>).

        Args:
            soup_element (Optional[Tag]): El elemento BeautifulSoup (o None).
            attribute (str): El nombre del atributo a obtener (ej: 'href', 'src', 'title').

        Returns:
            Optional[str]: El valor del atributo, o None si el elemento o el atributo no existen.
        """
        if soup_element:
            # Podemos acceder a los atributos como un diccionario. .get() devuelve None si no existe.
            return soup_element.get(attribute)
        else:
            return None

    def _build_url(self, relative_path: Optional[str]) -> Optional[str]:
        """
        Construye una URL absoluta a partir de una ruta relativa y la URL base del sitio.

        Útil cuando encuentras enlaces como '/oferta/123' y necesitas la URL completa.
        Requiere que 'base_url' esté definida en la configuración del scraper.

        Args:
            relative_path (Optional[str]): La ruta relativa encontrada (ej: '/empleo/xyz').

        Returns:
            Optional[str]: La URL absoluta construida, o None si falta la URL base o la ruta relativa.
        """
        if not relative_path or not self.base_url:
            logger.debug(f"[{self.source_name}] No se puede construir URL absoluta. Falta ruta relativa ('{relative_path}') o URL base ('{self.base_url}').")
            return None

        # Asegurarnos de que la URL base no tenga '/' al final y la ruta relativa sí tenga '/' al inicio
        # puede ser complicado. La forma más robusta es usar urllib.parse.urljoin,
        # ¡pero vamos a hacer una unión simple por ahora cuidando las barras!

        base = self.base_url.rstrip('/') # Quita la barra final de la base si existe
        path = relative_path.lstrip('/') # Quita la barra inicial de la ruta si existe

        # Podríamos necesitar lógica más avanzada si la URL base ya incluye una ruta.
        # Por ahora, una unión simple.
        full_url = f"{base}/{path}"
        logger.debug(f"[{self.source_name}] URL absoluta construida: {full_url}")
        return full_url


    def get_standard_job_dict(self) -> Dict[str, Any]:
        """
        Devuelve un diccionario vacío con las claves estándar esperadas para una oferta.

        Útil en las clases hijas para asegurar un formato de salida consistente.

        Returns:
            Dict[str, Any]: Diccionario con claves estándar inicializadas a None o valor por defecto.
        """
        return {
            'titulo': None,
            'empresa': None,
            'ubicacion': None,
            'descripcion': None,
            'fecha_publicacion': None,
            'url': None,
            'fuente': self.source_name # Pre-rellenamos la fuente.
            # Añadir aquí más campos estándar si definimos más adelante.
        }

# --- Fin de la Clase Base ---

# Ejemplo de cómo una clase hija la usaría (¡NO va en este archivo!):
# class ComputrabajoScraper(BaseScraper):
#     def __init__(self, http_client: HTTPClient, config: dict):
#         super().__init__(source_name="computrabajo", http_client=http_client, config=config)
#         # Podemos verificar aquí self.base_url si es indispensable.
#         if not self.base_url:
#              raise ValueError("ComputrabajoScraper requiere 'base_url' en la configuración.")

#     def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
#         logger.info(f"[{self.source_name}] Buscando trabajos con parámetros: {search_params}")
#         all_jobs = []
#         # 1. Construir la URL de búsqueda de Computrabajo
#         # ... lógica para crear la URL basada en self.base_url y search_params ...
#         search_url = f"{self.base_url}/ofertas-de-trabajo/?q={'%20'.join(search_params.get('keywords',[]))}" # Ejemplo simple

#         # 2. Bucle para manejar paginación (si existe)
#         page = 1
#         while True: # ¡Cuidado con bucles infinitos! Necesita condición de salida.
#              page_url = f"{search_url}&p={page}" # Ejemplo de URL de página
#              logger.debug(f"[{self.source_name}] Obteniendo página {page}: {page_url}")

#              # 3. Descargar HTML de la página de listado
#              html = self._fetch_html(page_url) # Usamos nuestro helper!
#              if not html:
#                  logger.warning(f"[{self.source_name}] No se pudo obtener HTML de la página {page}. Terminando paginación.")
#                  break # Salir del bucle si no podemos descargar la página

#              # 4. Parsear el HTML
#              soup = self._parse_html(html) # Usamos nuestro helper!
#              if not soup:
#                   logger.warning(f"[{self.source_name}] No se pudo parsear HTML de la página {page}. Terminando paginación.")
#                   break

#              # 5. Encontrar los contenedores de cada oferta en la página
#              job_cards = soup.select('div.oferta_card_selector') # ¡Selector CSS de ejemplo! Hay que inspeccionar la página real.
#              if not job_cards:
#                   logger.info(f"[{self.source_name}] No se encontraron más ofertas en la página {page}. Terminando búsqueda.")
#                   break # Condición de salida si no hay más ofertas

#              # 6. Extraer datos de cada tarjeta de oferta
#              for card in job_cards:
#                  oferta = self.get_standard_job_dict() # Empezamos con nuestro dict estándar.
#                  # Extraemos datos usando selectores CSS y nuestros helpers
#                  title_element = card.select_one('a.title_selector') # Selector de ejemplo
#                  oferta['titulo'] = self._safe_get_text(title_element)
#                  # ... extraer empresa, ubicación, etc. ...
#                  oferta['url'] = self._safe_get_attribute(title_element, 'href')
#                  # Podríamos necesitar construir URL absoluta si es relativa
#                  # oferta['url'] = self._build_url(oferta['url'])

#                  # Podría ser necesario ir a la página de detalle para la descripción completa
#                  # if oferta['url']:
#                  #     detail_html = self._fetch_html(oferta['url'])
#                  #     detail_soup = self._parse_html(detail_html)
#                  #     if detail_soup:
#                  #         desc_element = detail_soup.select_one('div.description_selector')
#                  #         oferta['descripcion'] = self._safe_get_text(desc_element)

#                  # Añadimos la oferta (si tiene datos mínimos, como URL y título)
#                  if oferta['url'] and oferta['titulo']:
#                      all_jobs.append(oferta)

#              # 7. Lógica para pasar a la siguiente página (o detectar si no hay más)
#              # ... buscar el botón/enlace "Siguiente", o comprobar si los resultados son < X ...
#              page += 1
#              # ¡Añadir un límite de páginas por seguridad sería buena idea!
#              # if page > MAX_PAGES: break

#         logger.info(f"[{self.source_name}] Se encontraron un total de {len(all_jobs)} ofertas.")
#         return all_jobs