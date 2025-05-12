# -*- coding: utf-8 -*-
# /src/scrapers/infojobs_scraper_improved.py

"""
Scraper mejorado para InfoJobs con:
- Mejor extracción de datos
- Procesamiento de páginas de detalle
- Estrategias anti-bloqueo
- Manejo robusto de errores
- Reintentos inteligentes
"""

import logging
import random
import re
import time
from typing import List, Dict, Any, Optional, Tuple, Union
from urllib.parse import quote_plus, urljoin, urlparse, parse_qs
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# Intentar importar el cliente HTTP mejorado
try:
    from src.utils.http_client_improved import ImprovedHTTPClient as HTTPClient
    IMPROVED_HTTP_CLIENT_AVAILABLE = True
except ImportError:
    from src.utils.http_client import HTTPClient
    IMPROVED_HTTP_CLIENT_AVAILABLE = False

# Importaciones principales
try:
    from src.scrapers.base_scraper import BaseScraper
    
    # Importar error_handler si está disponible
    try:
        from src.utils.error_handler import register_error, retry_on_failure
        ERROR_HANDLER_AVAILABLE = True
    except ImportError:
        ERROR_HANDLER_AVAILABLE = False
        # Funciones dummy si no está disponible
        def register_error(*args, **kwargs): pass
        def retry_on_failure(max_retries=3, base_delay=1):
            def decorator(func):
                return func
            return decorator
except ImportError as e:
    logging.basicConfig(level=logging.WARNING)
    logging.warning(f"Fallo al importar módulos de src en infojobs_scraper_improved: {e}")
    # Nos aseguramos de que el módulo pueda ser importado con stubs básicos
    class BaseScraper:
        def __init__(self, source_name, http_client, config): 
            self.source_name=source_name
            self.http_client=http_client
            self.config=config
            self.base_url=config.get('base_url') if config else None

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE = 10  # Aumentado de 5 a 10 para obtener más resultados

class InfojobsScraperImproved(BaseScraper):
    """
    Versión mejorada del scraper de InfoJobs con mejores técnicas de extracción
    y mayor robustez contra errores y bloqueos.
    """
    
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializa el scraper mejorado de InfoJobs.
        
        Args:
            http_client: Cliente HTTP para realizar peticiones
            config: Configuración específica para este scraper
        """
        super().__init__(source_name="infojobs", http_client=http_client, config=config)
        
        # Configurar URL base si no está especificada
        if not self.base_url:
            self.base_url = "https://www.infojobs.net"
            logger.warning(f"[{self.source_name}] 'base_url' no encontrada. Usando default: {self.base_url}")
        
        # Parámetros para el scraping
        self.config = config or {}
        self.process_detail_pages = self.config.get('process_detail_pages', True)
        self.max_detail_pages = self.config.get('max_detail_pages', 20)
        
        # Pool de user agents para rotación (serán usados si el cliente HTTP soporta setear user agents)
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
        ]
        
        # Estadísticas
        self.stats = {
            "pages_scraped": 0,
            "detail_pages_scraped": 0,
            "jobs_found": 0,
            "detail_success_rate": 0,
            "errors": 0
        }
    
    def _get_random_user_agent(self) -> str:
        """
        Obtiene un User-Agent aleatorio del pool.
        
        Returns:
            String con un User-Agent
        """
        return random.choice(self.user_agents)
    
    def _build_search_url(self, keywords: List[str], location: Optional[str] = None, page: int = 1) -> str:
        """
        Construye la URL de búsqueda con los parámetros proporcionados.
        
        Args:
            keywords: Palabras clave para la búsqueda
            location: Ubicación para filtrar (opcional)
            page: Número de página
            
        Returns:
            URL completa para la búsqueda
        """
        query = quote_plus(" ".join(keywords)) if keywords else ""
        path = "/jobsearch/search-results/list.xhtml"
        
        params = f"?keyword={query}&page={page}"
        
        # Añadir ubicación si está disponible
        if location:
            location_encoded = quote_plus(location)
            params += f"&provinceIds={location_encoded}"
        
        # Añadir filtros adicionales para tecnología y desarrollo
        params += "&category=informatica-telecomunicaciones"
        
        full_url = f"{self.base_url.rstrip('/')}{path}{params}"
        logger.debug(f"[{self.source_name}] URL construida: {full_url}")
        return full_url
    
    def _build_url(self, href: Optional[str]) -> Optional[str]:
        """
        Construye una URL absoluta a partir de una URL relativa.
        
        Args:
            href: URL relativa o absoluta
            
        Returns:
            URL absoluta o None si no se pudo construir
        """
        if not href:
            return None
            
        # Si ya es una URL completa, devolverla directamente
        if href.startswith(('http://', 'https://')):
            return href
            
        # Construir URL completa
        return urljoin(self.base_url, href)
    
    @retry_on_failure(max_retries=3, base_delay=2)
    def _fetch_html(self, url: str) -> Optional[str]:
        """
        Obtiene el HTML de una URL con reintentos y rotación de User-Agent.
        
        Args:
            url: URL a obtener
            
        Returns:
            Contenido HTML como string o None si hay error
        """
        try:
            # Si el cliente HTTP soporta headers personalizados, usar user agent aleatorio
            headers = None
            if IMPROVED_HTTP_CLIENT_AVAILABLE:
                headers = {
                    'User-Agent': self._get_random_user_agent(),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
                    'Referer': self.base_url,
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0',
                }
            
            response = self.http_client.get(url, headers=headers)
            return response.text
        except Exception as e:
            logger.error(f"[{self.source_name}] Error al obtener HTML de {url}: {str(e)}")
            register_error('html_fetch_error', self.source_name, f"URL {url}: {str(e)}")
            raise
    
    def _parse_html(self, html: str) -> BeautifulSoup:
        """
        Convierte el HTML en un objeto BeautifulSoup para su análisis.
        
        Args:
            html: Contenido HTML como string
            
        Returns:
            Objeto BeautifulSoup
        """
        try:
            return BeautifulSoup(html, 'html.parser')
        except Exception as e:
            logger.error(f"[{self.source_name}] Error al parsear HTML: {str(e)}")
            register_error('html_parse_error', self.source_name, str(e))
            # Devolver un objeto vacío en caso de error
            return BeautifulSoup("", 'html.parser')
    
    def _safe_get_text(self, element) -> str:
        """
        Extrae texto de un elemento de forma segura.
        
        Args:
            element: Elemento BeautifulSoup
            
        Returns:
            Texto extraído o string vacío si hay error
        """
        if not element:
            return ""
        try:
            return element.get_text(strip=True)
        except Exception:
            return ""
    
    def _safe_get_attribute(self, element, attr: str) -> Optional[str]:
        """
        Obtiene un atributo de un elemento de forma segura.
        
        Args:
            element: Elemento BeautifulSoup
            attr: Nombre del atributo a extraer
            
        Returns:
            Valor del atributo o None si no existe o hay error
        """
        if not element:
            return None
        try:
            return element.get(attr)
        except Exception:
            return None
    
    def _extract_job_id(self, url: str) -> Optional[str]:
        """
        Extrae el ID de la oferta de la URL.
        
        Args:
            url: URL de la oferta
            
        Returns:
            ID de la oferta o None si no se pudo extraer
        """
        if not url:
            return None
            
        # Intentar extraer por patrón de URL
        try:
            # Patrones típicos de InfoJobs:
            # /oferta/titulo-oferta/provincia/of-i12345678901234567890
            # /oferta/titulo/of-i12345678901234567890
            id_match = re.search(r'of-i(\d+)', url)
            if id_match:
                return f"infojobs_{id_match.group(1)}"
                
            # Alternativa: extraer de parámetros de URL
            parsed_url = urlparse(url)
            params = parse_qs(parsed_url.query)
            
            if 'oid' in params:
                return f"infojobs_{params['oid'][0]}"
        except Exception:
            pass
            
        # Si no podemos extraer un ID específico, usar un hash de la URL
        return f"infojobs_{hash(url) % 10000000000}"
    
    def _parse_date(self, date_text: str) -> str:
        """
        Convierte textos de fecha en formato estándar YYYY-MM-DD.
        
        Args:
            date_text: Texto de fecha en formato de InfoJobs (ej: "Hace 2 días")
            
        Returns:
            Fecha en formato YYYY-MM-DD
        """
        today = datetime.today()
        
        # Formato InfoJobs típico
        if not date_text or date_text.strip() == "":
            return today.strftime("%Y-%m-%d")
        
        date_text = date_text.lower().strip()
        
        # Patrones comunes de InfoJobs
        if "publicada hoy" in date_text or "hace" in date_text and "hora" in date_text:
            return today.strftime("%Y-%m-%d")
        elif "hace" in date_text and "día" in date_text:
            try:
                days = re.search(r"hace\s+(\d+)\s+día", date_text)
                if days:
                    days_ago = int(days.group(1))
                    date = today - timedelta(days=days_ago)
                    return date.strftime("%Y-%m-%d")
            except Exception:
                pass
        elif "publicada ayer" in date_text:
            date = today - timedelta(days=1)
            return date.strftime("%Y-%m-%d")
        elif "publicada el" in date_text:
            # Formato "Publicada el 15 de agosto"
            try:
                date_match = re.search(r"(\d+)\s+de\s+([a-zA-Zá-úÁ-Ú]+)", date_text)
                if date_match:
                    day = int(date_match.group(1))
                    month_name = date_match.group(2).lower()
                    
                    month_map = {
                        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
                        "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
                    }
                    
                    month = month_map.get(month_name, today.month)
                    year = today.year if month <= today.month else today.year - 1
                    
                    return f"{year}-{month:02d}-{day:02d}"
            except Exception:
                pass
        
        # Si no podemos parsear, devolver la fecha actual
        return today.strftime("%Y-%m-%d")
    
    def _extract_salary(self, detail_soup: BeautifulSoup) -> Optional[str]:
        """
        Extrae información de salario de la página de detalle.
        
        Args:
            detail_soup: BeautifulSoup de la página de detalle
            
        Returns:
            Texto con la información de salario o None si no está disponible
        """
        try:
            # Intentar diferentes selectores para el salario
            salary_selectors = [
                "div.text-body-2 span.body-xs-bold",
                "ul.list-default li:contains('Salario')",
                "div.mt-20:contains('Salario')",
                "span.header-salary"
            ]
            
            for selector in salary_selectors:
                salary_element = detail_soup.select_one(selector)
                if salary_element:
                    salary_text = self._safe_get_text(salary_element)
                    # Eliminar textos innecesarios
                    salary_text = salary_text.replace("Salario:", "").strip()
                    if salary_text and salary_text.lower() != "no especificado":
                        return salary_text
        except Exception as e:
            logger.debug(f"[{self.source_name}] Error al extraer salario: {str(e)}")
        
        return None
    
    def _extract_work_mode(self, detail_soup: BeautifulSoup) -> str:
        """
        Extrae la modalidad de trabajo (presencial, remoto, híbrido).
        
        Args:
            detail_soup: BeautifulSoup de la página de detalle
            
        Returns:
            Modalidad de trabajo como string
        """
        try:
            # Buscar información de modalidad en la página
            mode_selectors = [
                "ul.list-default li:contains('Teletrabajo')",
                "div.mt-20:contains('Teletrabajo')",
                "div.mt-20:contains('Presencial')"
            ]
            
            for selector in mode_selectors:
                mode_element = detail_soup.select_one(selector)
                if mode_element:
                    mode_text = self._safe_get_text(mode_element).lower()
                    
                    if any(term in mode_text for term in ["100% en remoto", "teletrabajo total"]):
                        return "Remoto"
                    elif any(term in mode_text for term in ["híbrido", "teletrabajo parcial"]):
                        return "Híbrido"
                    elif any(term in mode_text for term in ["presencial", "sin teletrabajo"]):
                        return "Presencial"
            
            # Buscar en la descripción completa
            description = detail_soup.select_one("div.detail-description")
            if description:
                desc_text = self._safe_get_text(description).lower()
                
                if any(term in desc_text for term in ["100% remoto", "teletrabajo total", "full remote"]):
                    return "Remoto"
                elif any(term in desc_text for term in ["híbrido", "teletrabajo parcial", "remote friendly"]):
                    return "Híbrido"
        except Exception as e:
            logger.debug(f"[{self.source_name}] Error al extraer modalidad: {str(e)}")
        
        # Por defecto, asumir presencial
        return "Presencial"
    
    def _extract_requirements(self, detail_soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extrae requisitos y detalles adicionales de la oferta.
        
        Args:
            detail_soup: BeautifulSoup de la página de detalle
            
        Returns:
            Diccionario con requisitos y experiencia
        """
        requirements = {
            "experiencia": None,
            "estudios": None,
            "jornada": None,
            "contrato": None
        }
        
        try:
            # Buscar sección de requisitos
            req_section = detail_soup.select_one("div.list-default")
            if req_section:
                # Buscar elementos de requisitos
                req_items = req_section.select("li")
                
                for item in req_items:
                    item_text = self._safe_get_text(item).lower()
                    
                    if "experiencia" in item_text:
                        requirements["experiencia"] = item_text.replace("experiencia mínima:", "").strip()
                    elif "estudios" in item_text:
                        requirements["estudios"] = item_text.replace("estudios mínimos:", "").strip()
                    elif "jornada" in item_text:
                        requirements["jornada"] = item_text.replace("tipo de jornada:", "").strip()
                    elif "contrato" in item_text:
                        requirements["contrato"] = item_text.replace("tipo de contrato:", "").strip()
        except Exception as e:
            logger.debug(f"[{self.source_name}] Error al extraer requisitos: {str(e)}")
        
        return requirements
    
    def _process_detail_page(self, url: str) -> Dict[str, Any]:
        """
        Procesa una página de detalle para extraer información adicional.
        
        Args:
            url: URL de la página de detalle
            
        Returns:
            Diccionario con información adicional
        """
        additional_info = {
            "salario": None,
            "modalidad": "Presencial",  # Por defecto
            "experiencia": None,
            "estudios": None,
            "jornada": None,
            "contrato": None,
            "descripcion_completa": None
        }
        
        try:
            # Añadir delay aleatorio para evitar bloqueo
            time.sleep(random.uniform(1.0, 2.5))
            
            # Obtener y procesar página
            html = self._fetch_html(url)
            if not html:
                return additional_info
                
            detail_soup = self._parse_html(html)
            
            # Extraer información adicional
            additional_info["salario"] = self._extract_salary(detail_soup)
            additional_info["modalidad"] = self._extract_work_mode(detail_soup)
            
            # Extraer requisitos
            requirements = self._extract_requirements(detail_soup)
            additional_info.update(requirements)
            
            # Extraer descripción completa
            description_element = detail_soup.select_one("div.detail-description")
            if description_element:
                additional_info["descripcion_completa"] = self._safe_get_text(description_element)
            
            # Actualizar estadísticas
            self.stats["detail_pages_scraped"] += 1
            self.stats["detail_success_rate"] = self.stats["detail_pages_scraped"] / (self.stats["detail_pages_scraped"] + self.stats["errors"])
            
            return additional_info
            
        except Exception as e:
            logger.error(f"[{self.source_name}] Error al procesar página de detalle {url}: {str(e)}")
            register_error('detail_page_error', self.source_name, f"URL {url}: {str(e)}")
            self.stats["errors"] += 1
            return additional_info
    
    def _extract_job_from_card(self, card) -> Optional[Dict[str, Any]]:
        """
        Extrae información de una oferta a partir de una tarjeta de resultados.
        
        Args:
            card: Elemento BeautifulSoup de la tarjeta
            
        Returns:
            Diccionario con la información de la oferta o None si hay error
        """
        try:
            oferta = self.get_standard_job_dict()
            oferta['fuente'] = self.source_name
            
            # Extraer título y URL
            title_element = card.select_one("a.js-o-link, h2.Headings__H4-sc-1jkn9ay-3 a, h2 a")
            if not title_element:
                title_element = card.select_one("h2 a")  # Selector alternativo
                
            oferta["titulo"] = self._safe_get_text(title_element)
            href = self._safe_get_attribute(title_element, "href")
            oferta["url"] = self._build_url(href)
            
            # Extraer ID
            oferta["id"] = self._extract_job_id(oferta["url"])
            
            # Extraer empresa
            empresa_element = card.select_one("span.nom-emp, span.Link__LinkBase-sc-ko91uh-0, a.Text-sc-19ub5mn-0")
            oferta["empresa"] = self._safe_get_text(empresa_element)
            
            # Extraer ubicación
            ubicacion_element = card.select_one("span.location, li[data-cy='location']")
            oferta["ubicacion"] = self._safe_get_text(ubicacion_element)
            
            # Extraer fecha
            fecha_element = card.select_one("span.date, span[data-cy='published']")
            fecha_texto = self._safe_get_text(fecha_element)
            oferta["fecha_publicacion"] = self._parse_date(fecha_texto)
            
            # Extraer descripción breve
            desc_element = card.select_one("div.description, div[data-cy='job-content'], p.Text-sc-19ub5mn-0.Mhpis")
            oferta["descripcion"] = self._safe_get_text(desc_element)
            
            # Validar datos mínimos
            if not oferta["titulo"] or not oferta["url"]:
                logger.debug(f"[{self.source_name}] Oferta descartada por datos incompletos")
                return None
                
            return oferta
            
        except Exception as e:
            logger.error(f"[{self.source_name}] Error al extraer oferta: {str(e)}")
            register_error('job_card_error', self.source_name, str(e))
            return None
    
    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Obtiene ofertas de trabajo usando los parámetros proporcionados.
        
        Args:
            search_params: Parámetros para la búsqueda de ofertas
            
        Returns:
            Lista de ofertas de trabajo
        """
        logger.info(f"[{self.source_name}] Iniciando scraping con parámetros: {search_params}")
        all_offers = []
        detail_urls = []
        
        # Configurar parámetros de búsqueda
        keywords = search_params.get("keywords", [])
        location = search_params.get("location")
        
        # Determinar si procesar páginas de detalle
        process_detail = search_params.get("process_detail_pages", self.process_detail_pages)
        
        # Si no hay keywords, no podemos buscar
        if not keywords:
            logger.warning(f"[{self.source_name}] No se proporcionaron palabras clave para la búsqueda")
            return all_offers
        
        # Iniciar scraping de páginas de resultados
        current_page = 1
        
        while current_page <= MAX_PAGES_TO_SCRAPE:
            try:
                url = self._build_search_url(keywords, location, page=current_page)
                logger.info(f"[{self.source_name}] Procesando página {current_page}: {url}")
                
                # Añadir delay aleatorio entre páginas
                if current_page > 1:
                    time.sleep(random.uniform(2.0, 4.0))
                
                html = self._fetch_html(url)
                if not html:
                    logger.warning(f"[{self.source_name}] No se pudo obtener HTML de página {current_page}")
                    break
                
                soup = self._parse_html(html)
                
                # Intentar diferentes selectores para las tarjetas de ofertas
                card_selectors = [
                    "div.elemento", 
                    "ol.Container-sc-1q37ai0-0 li", 
                    "div.ij-OfferCard",
                    ".oc-item"
                ]
                
                job_cards = None
                for selector in card_selectors:
                    job_cards = soup.select(selector)
                    if job_cards and len(job_cards) > 0:
                        break
                
                if not job_cards or len(job_cards) == 0:
                    logger.info(f"[{self.source_name}] No hay más ofertas en página {current_page}.")
                    break
                
                # Extraer información de cada tarjeta
                for card in job_cards:
                    oferta = self._extract_job_from_card(card)
                    
                    if oferta:
                        # Añadir a resultados
                        all_offers.append(oferta)
                        
                        # Si procesamos detalles, guardar URL para procesar después
                        if process_detail and oferta["url"]:
                            detail_urls.append(oferta["url"])
                
                # Actualizar estadísticas
                self.stats["pages_scraped"] += 1
                
                # Pasar a la siguiente página
                current_page += 1
                
                # Si no hay suficientes tarjetas, probablemente estamos en la última página
                if job_cards and len(job_cards) < 10:
                    logger.info(f"[{self.source_name}] Pocas ofertas ({len(job_cards)}) en página {current_page-1}, finalizando paginación.")
                    break
                
            except Exception as e:
                logger.error(f"[{self.source_name}] Error procesando página {current_page}: {str(e)}")
                register_error('page_error', self.source_name, f"Página {current_page}: {str(e)}")
                self.stats["errors"] += 1
                # Continuar con la siguiente página en caso de error
                current_page += 1
        
        # Procesar páginas de detalle si está habilitado
        if process_detail and detail_urls:
            logger.info(f"[{self.source_name}] Procesando {len(detail_urls)} páginas de detalle")
            
            # Limitar el número de páginas de detalle si hay demasiadas
            if len(detail_urls) > self.max_detail_pages:
                logger.info(f"[{self.source_name}] Limitando a {self.max_detail_pages} páginas de detalle de {len(detail_urls)} disponibles")
                detail_urls = detail_urls[:self.max_detail_pages]
            
            # Procesar detalles y enriquecer ofertas
            for i, detail_url in enumerate(detail_urls):
                try:
                    # Encontrar la oferta correspondiente
                    job_id = self._extract_job_id(detail_url)
                    matching_offers = [offer for offer in all_offers 
                                      if offer.get("id") == job_id or offer.get("url") == detail_url]
                    
                    if not matching_offers:
                        continue
                    
                    # Obtener información adicional
                    additional_info = self._process_detail_page(detail_url)
                    
                    # Actualizar la oferta con la información adicional
                    for key, value in additional_info.items():
                        if value and (key not in matching_offers[0] or not matching_offers[0][key]):
                            matching_offers[0][key] = value
                    
                    # Si tenemos una descripción completa, reemplazar la breve
                    if additional_info.get("descripcion_completa"):
                        matching_offers[0]["descripcion"] = additional_info["descripcion_completa"]
                    
                    logger.debug(f"[{self.source_name}] Página de detalle {i+1}/{len(detail_urls)} procesada: {detail_url}")
                    
                except Exception as e:
                    logger.error(f"[{self.source_name}] Error al procesar detalle {detail_url}: {str(e)}")
                    register_error('detail_enrich_error', self.source_name, f"URL {detail_url}: {str(e)}")
                    self.stats["errors"] += 1
        
        # Actualizar estadísticas finales
        self.stats["jobs_found"] = len(all_offers)
        
        logger.info(f"[{self.source_name}] Estadísticas: {self.stats['pages_scraped']} páginas, "
                   f"{self.stats['detail_pages_scraped']} detalles, {self.stats['jobs_found']} ofertas")
        logger.info(f"[{self.source_name}] Total de ofertas obtenidas: {len(all_offers)}")
        
        return all_offers
