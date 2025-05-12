# -*- coding: utf-8 -*-
# /src/scrapers/linkedin_scraper_improved.py

"""
Versión mejorada del scraper para LinkedIn Jobs.
Incluye manejo robusto de errores, anti-bloqueo avanzado, filtros optimizados y
soporte para el cliente HTTP mejorado si está disponible.
"""

import logging
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import quote_plus, urljoin, urlparse
import time
import random
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient
from src.utils.helpers import process_date

# Intentar importar el cliente HTTP mejorado si está disponible
try:
    from src.utils.http_client_improved import ImprovedHTTPClient
    IMPROVED_CLIENT_AVAILABLE = True
except ImportError:
    IMPROVED_CLIENT_AVAILABLE = False
    
# Intentar importar el manejador de errores si está disponible
try:
    from src.utils.error_handler import retry_on_failure, safe_request_handler, register_error
    ERROR_HANDLER_AVAILABLE = True
except ImportError:
    ERROR_HANDLER_AVAILABLE = False

logger = logging.getLogger(__name__)

# Configuración del scraper
MAX_PAGES_TO_SCRAPE = 10  # Aumentado pero con cuidado
RETRY_DELAY_BASE = 2  # Segundos de base para espera entre reintentos
MAX_RETRIES = 3  # Máximo de reintentos por página

class LinkedInScraperImproved(BaseScraper):
    """
    Scraper mejorado para LinkedIn Jobs que extrae ofertas de trabajo con mejor manejo de errores.
    
    Características:
    - Usa el cliente HTTP mejorado si está disponible
    - Implementa estrategias anti-bloqueo avanzadas
    - Diversifica los parámetros de búsqueda para maximizar resultados
    - Maneja errores de forma robusta para continuar incluso con problemas
    - Recolecta datos más detallados de las ofertas
    """
    
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """Inicializa el scraper con mejoras de robustez y anti-bloqueo."""
        super().__init__(source_name="linkedin", http_client=http_client, config=config)
        
        # Configurar URL base
        if not self.base_url:
            self.base_url = "https://www.linkedin.com/jobs/search/"
            logger.warning(f"[{self.source_name}] 'base_url' no encontrada. Usando default: {self.base_url}")
        
        # Verificar si estamos usando el cliente HTTP mejorado
        self.using_improved_client = IMPROVED_CLIENT_AVAILABLE and isinstance(http_client, ImprovedHTTPClient)
        if self.using_improved_client:
            logger.info(f"[{self.source_name}] Utilizando cliente HTTP mejorado con manejo robusto de errores")
        
        # Pool de User Agents para rotación
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.2277.112'
        ]
        
        # Configuración para control de frecuencia y reintentos
        self.request_delay = config.get('request_delay_seconds', 2.5) if config else 2.5
        self.max_retries = config.get('max_retries', MAX_RETRIES) if config else MAX_RETRIES
        self.error_count = 0
        self.success_count = 0
        
        # Estadísticas de ejecución
        self.stats = {
            'pages_processed': 0,
            'jobs_found': 0,
            'failed_requests': 0,
            'retries': 0
        }

    def _get_headers(self) -> Dict[str, str]:
        """Genera headers aleatorios para cada petición."""
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.linkedin.com/',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'DNT': '1',  # Do Not Track
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1'
        }
        return headers

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        """
        Construye la URL para buscar trabajos en LinkedIn con filtros optimizados.
        
        Args:
            keywords: Lista de palabras clave para buscar
            location: Ubicación para filtrar
            page: Número de página para resultados
            
        Returns:
            URL completa para realizar la búsqueda
        """
        if not self.base_url:
            logger.error(f"[{self.source_name}] No se puede construir URL sin 'base_url'.")
            return None

        # Construir keywords en formato LinkedIn
        if not keywords:
            keywords = ["data", "scientist", "developer", "engineer", "python"]
            
        # Usar diferentes combinaciones dependiendo del número de página
        # para diversificar resultados
        if len(keywords) > 6:
            if page % 2 == 0:
                # Páginas pares: enfoque en tecnologías
                tech_keywords = [k for k in keywords if k.lower() in [
                    'python', 'sql', 'java', 'javascript', 'react', 'node', 
                    'r', 'pandas', 'spark', 'aws', 'azure', 'gcp', 'machine learning'
                ]]
                if tech_keywords:
                    selected_keywords = tech_keywords[:3]
                else:
                    selected_keywords = keywords[:3]
            else:
                # Páginas impares: enfoque en roles
                role_keywords = [k for k in keywords if k.lower() in [
                    'data scientist', 'developer', 'engineer', 'analyst', 
                    'architect', 'devops', 'frontend', 'backend', 'full stack'
                ]]
                if role_keywords:
                    selected_keywords = role_keywords[:3]
                else:
                    selected_keywords = keywords[:3]
        else:
            selected_keywords = keywords[:3]
            
        keyword_query = " ".join(selected_keywords)
        keyword_param = quote_plus(keyword_query)
        
        # Mapear ubicación con manejo mejorado
        location_param = ""
        remote_param = ""
        
        if location:
            # Detectar si busca trabajo remoto
            if any(term in location.lower() for term in ['remote', 'remoto', 'teletrabajo', 'trabajo a distancia']):
                remote_param = "&f_WT=2"  # Filtro de LinkedIn para trabajos remotos
                
                # Si además tiene una ubicación específica, la añadimos
                location_clean = location.lower()
                for remote_term in ['remote', 'remoto', 'teletrabajo', 'trabajo a distancia']:
                    location_clean = location_clean.replace(remote_term, '').strip()
                
                if location_clean:
                    location_param = f"&location={quote_plus(location_clean)}"
            else:
                location_param = f"&location={quote_plus(location)}"
        
        # Construir URL base con parámetros
        url = f"{self.base_url}?keywords={keyword_param}{location_param}{remote_param}"
        
        # Añadir parámetros adicionales para mejorar resultados
        url += "&sortBy=R"  # Ordenar por relevancia
        url += "&f_TPR=r2592000"  # Últimos 30 días (2,592,000 segundos)
        
        # Añadir filtros de experiencia para diversificar resultados
        if page % 3 == 0:
            url += "&f_E=2"  # Entry level
        elif page % 3 == 1:
            url += "&f_E=3"  # Mid-Senior level
        # Si es page % 3 == 2, no añadimos filtro para obtener todos los niveles
        
        # Añadir paginación
        if page > 1:
            start = (page - 1) * 25  # LinkedIn muestra 25 resultados por página
            url += f"&start={start}"
        
        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {url}")
        return url

    def _fetch_html_with_retry(self, url: str, max_retries: int = 3) -> Optional[str]:
        """
        Obtiene el HTML de una URL con reintentos inteligentes.
        
        Args:
            url: URL a descargar
            max_retries: Número máximo de reintentos
            
        Returns:
            Contenido HTML o None si falla
        """
        if ERROR_HANDLER_AVAILABLE and hasattr(safe_request_handler, '__call__'):
            # Si tenemos el manejador de errores, lo usamos
            @safe_request_handler
            def _fetch_with_handler():
                headers = self._get_headers()
                return self._fetch_html(url, headers=headers)
            
            return _fetch_with_handler()
        else:
            # Implementación manual de reintentos
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        # Espera exponencial con jitter
                        wait_time = RETRY_DELAY_BASE * (2 ** attempt) + random.uniform(0.1, 1.0)
                        logger.info(f"[{self.source_name}] Reintento {attempt+1}/{max_retries} para URL {url} en {wait_time:.2f}s")
                        time.sleep(wait_time)
                        self.stats['retries'] += 1
                    
                    # Rotar headers en cada intento
                    headers = self._get_headers()
                    html = self._fetch_html(url, headers=headers)
                    
                    if html:
                        self.success_count += 1
                        return html
                except Exception as e:
                    logger.error(f"[{self.source_name}] Error en intento {attempt+1}: {str(e)}")
                    continue
            
            # Si llegamos aquí, todos los intentos fallaron
            self.error_count += 1
            self.stats['failed_requests'] += 1
            logger.error(f"[{self.source_name}] Fallaron todos los reintentos para URL: {url}")
            return None

    def _parse_linkedin_date(self, date_text: Optional[str]) -> Optional[str]:
        """
        Parsea el formato de fecha de LinkedIn a formato ISO.
        
        Args:
            date_text: Texto de fecha de LinkedIn (ej: "hace 3 días", "publicado hoy", etc.)
            
        Returns:
            Fecha en formato ISO YYYY-MM-DD o None si no se puede parsear
        """
        if not date_text:
            return None
        
        # Limpiar el texto
        date_text = date_text.lower().strip()
        
        today = datetime.now().date()
        
        # Patrones comunes en LinkedIn (español e inglés)
        if "hoy" in date_text or "today" in date_text:
            return today.isoformat()
        
        if "ayer" in date_text or "yesterday" in date_text:
            return (today - timedelta(days=1)).isoformat()
        
        # Patrones como "hace X días/semanas/meses"
        dias_match = re.search(r'hace\s+(\d+)\s+d[ií]as?', date_text)
        if dias_match:
            dias = int(dias_match.group(1))
            return (today - timedelta(days=dias)).isoformat()
            
        semanas_match = re.search(r'hace\s+(\d+)\s+semanas?', date_text)
        if semanas_match:
            semanas = int(semanas_match.group(1))
            return (today - timedelta(weeks=semanas)).isoformat()
            
        meses_match = re.search(r'hace\s+(\d+)\s+meses?', date_text)
        if meses_match:
            meses = int(meses_match.group(1))
            # Aproximación simple: un mes = 30 días
            return (today - timedelta(days=30*meses)).isoformat()
        
        # Patrones en inglés
        days_match = re.search(r'(\d+)\s+days?\s+ago', date_text)
        if days_match:
            days = int(days_match.group(1))
            return (today - timedelta(days=days)).isoformat()
            
        weeks_match = re.search(r'(\d+)\s+weeks?\s+ago', date_text)
        if weeks_match:
            weeks = int(weeks_match.group(1))
            return (today - timedelta(weeks=weeks)).isoformat()
            
        months_match = re.search(r'(\d+)\s+months?\s+ago', date_text)
        if months_match:
            months = int(months_match.group(1))
            return (today - timedelta(days=30*months)).isoformat()
        
        # Si los patrones específicos fallan, intentar con el helper general
        result = process_date(date_text)
        if result:
            return result
        
        # Si todo falla, devolvemos una fecha de hace 7 días (estimación)
        return (today - timedelta(days=7)).isoformat()

    def _extract_job_details(self, card: BeautifulSoup) -> Dict[str, Any]:
        """
        Extrae detalles de una tarjeta de oferta de trabajo.
        
        Args:
            card: Elemento BeautifulSoup con la tarjeta de trabajo
            
        Returns:
            Diccionario con los detalles de la oferta
        """
        job = self.get_standard_job_dict()
        
        try:
            # Extraer título
            title_elem = card.select_one('h3.base-search-card__title, h3.job-card-list__title')
            job['titulo'] = self._safe_get_text(title_elem)
            
            # Extraer empresa
            company_elem = card.select_one('h4.base-search-card__subtitle, h4.job-card-container__company-name')
            job['empresa'] = self._safe_get_text(company_elem)
            
            # Extraer ubicación
            location_elem = card.select_one('span.job-search-card__location, span.job-card-container__metadata-item')
            job['ubicacion'] = self._safe_get_text(location_elem)
            
            # Extraer URL
            url_elem = card.select_one('a.base-card__full-link, a.job-card-container__link')
            job_url = self._safe_get_attribute(url_elem, 'href')
            if job_url:
                # Limpiar URL (LinkedIn a veces añade parámetros de tracking)
                job_url = job_url.split('?')[0]
                job['url'] = job_url
            
            # Extraer fecha
            date_elem = card.select_one('time.job-search-card__listdate, time.job-card-container__posted-date')
            date_text = self._safe_get_attribute(date_elem, 'datetime')
            if date_text:
                job['fecha_publicacion'] = date_text[:10]  # YYYY-MM-DD
            else:
                date_text = self._safe_get_text(card.select_one('time, span.job-search-card__listdate, span.job-card-container__posted-date'))
                job['fecha_publicacion'] = self._parse_linkedin_date(date_text)
            
            # Extraer descripción corta (si está disponible)
            desc_elem = card.select_one('p.base-card__metadata, p.job-card-container__metadata-item')
            short_desc = self._safe_get_text(desc_elem)
            if short_desc:
                job['descripcion'] = short_desc
            
            # Extraer etiquetas o características adicionales
            tags_elems = card.select('li.base-search-card__metadata-item, li.job-card-container__metadata-item')
            tags = [self._safe_get_text(tag) for tag in tags_elems if tag]
            if tags:
                job['descripcion'] = (job['descripcion'] or '') + f"\nCaracterísticas: {', '.join(tags)}"
                
            # Extraer salario si está disponible
            salary_elem = card.select_one('.job-search-card__salary-info, .job-card-container__salary-info')
            if salary_elem:
                salary_text = self._safe_get_text(salary_elem)
                if salary_text:
                    job['descripcion'] = (job['descripcion'] or '') + f"\nSalario: {salary_text}"
            
            # Extraer modalidad (remoto, presencial, híbrido)
            remote_elem = card.select_one('.job-search-card__benefits, .job-card-container__benefits')
            if remote_elem:
                remote_text = self._safe_get_text(remote_elem)
                if remote_text:
                    job['descripcion'] = (job['descripcion'] or '') + f"\nModalidad: {remote_text}"
            
            # Añadir fuente
            job['fuente'] = self.source_name
        except Exception as e:
            logger.error(f"[{self.source_name}] Error extrayendo detalles de oferta: {e}")
        
        return job

    def _process_job_detail_page(self, job_url: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Obtiene datos adicionales de la página de detalle de la oferta si es posible.
        
        Args:
            job_url: URL de la página de detalle
            job_data: Datos ya extraídos de la oferta
            
        Returns:
            Datos de la oferta enriquecidos
        """
        try:
            # Añadir delay para evitar ser bloqueados
            time.sleep(random.uniform(1.5, 3.0))
            
            # Obtener HTML de la página de detalle
            html_content = self._fetch_html_with_retry(job_url)
            if not html_content:
                return job_data
                
            soup = self._parse_html(html_content)
            if not soup:
                return job_data
                
            # Extraer descripción completa
            desc_elem = soup.select_one('div.description__text, div.show-more-less-html__markup')
            if desc_elem:
                full_desc = self._safe_get_text(desc_elem)
                if full_desc:
                    # Si ya tenemos una descripción corta, la complementamos
                    if job_data.get('descripcion'):
                        job_data['descripcion'] += f"\n\nDescripción completa:\n{full_desc}"
                    else:
                        job_data['descripcion'] = full_desc
            
            # Extraer criterios, beneficios o detalles adicionales
            criteria_elems = soup.select('li.description__job-criteria-item')
            if criteria_elems:
                criteria = []
                for elem in criteria_elems:
                    header = self._safe_get_text(elem.select_one('h3'))
                    value = self._safe_get_text(elem.select_one('span'))
                    if header and value:
                        criteria.append(f"{header}: {value}")
                
                if criteria:
                    job_data['descripcion'] = (job_data.get('descripcion') or '') + f"\n\nDetalles adicionales:\n" + "\n".join(criteria)
            
            # Extraer empresa con más detalles
            company_elem = soup.select_one('a.topcard__org-name-link, span.topcard__org-name-text')
            if company_elem:
                company_name = self._safe_get_text(company_elem)
                if company_name and not job_data.get('empresa'):
                    job_data['empresa'] = company_name
                    
            # Ubicación con más detalles
            location_elem = soup.select_one('span.topcard__flavor, span.topcard__flavor--bullet')
            if location_elem:
                location_text = self._safe_get_text(location_elem)
                if location_text and not job_data.get('ubicacion'):
                    job_data['ubicacion'] = location_text
                    
        except Exception as e:
            logger.error(f"[{self.source_name}] Error procesando página de detalle {job_url}: {e}")
        
        return job_data

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Método principal que obtiene ofertas de trabajo de LinkedIn de forma robusta.
        
        Args:
            search_params: Diccionario con parámetros de búsqueda (keywords, location)
            
        Returns:
            Lista de ofertas de trabajo normalizadas
        """
        logger.info(f"[{self.source_name}] Iniciando búsqueda con parámetros: {search_params}")
        all_job_listings = []
        
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', '')
        process_detail_pages = search_params.get('process_detail_pages', False)
        
        # Limitar el número de keywords para evitar sobrecarga
        if len(keywords) > 3:
            # Priorizar términos relacionados con datos
            data_keywords = [kw for kw in keywords if any(term in kw.lower() for term in 
                                                         ['data', 'datos', 'analytics', 'análisis', 
                                                          'scientist', 'machine learning', 'python', 'sql'])]
            if data_keywords:
                keywords = data_keywords[:3]
            else:
                keywords = keywords[:3]
            
        current_page = 1
        consecutive_failures = 0
        
        while current_page <= MAX_PAGES_TO_SCRAPE:
            logger.info(f"[{self.source_name}] Procesando página {current_page}...")
            self.stats['pages_processed'] += 1
            
            url = self._build_search_url(keywords, location, current_page)
            if not url:
                logger.error(f"[{self.source_name}] Error construyendo URL para página {current_page}")
                break
                
            # Añadir pequeño delay para evitar bloqueos
            time.sleep(random.uniform(self.request_delay, self.request_delay * 1.5))
            
            # Usar fetch con reintentos
            html_content = self._fetch_html_with_retry(url, max_retries=self.max_retries)
            if not html_content:
                logger.warning(f"[{self.source_name}] No se pudo obtener HTML de página {current_page}")
                consecutive_failures += 1
                if consecutive_failures >= 2:
                    logger.error(f"[{self.source_name}] Demasiados fallos consecutivos, terminando búsqueda.")
                    break
                current_page += 1
                continue
                
            soup = self._parse_html(html_content)
            if not soup:
                logger.warning(f"[{self.source_name}] No se pudo parsear HTML de página {current_page}")
                consecutive_failures += 1
                if consecutive_failures >= 2:
                    logger.error(f"[{self.source_name}] Demasiados fallos consecutivos, terminando búsqueda.")
                    break
                current_page += 1
                continue
            
            # Reiniciar contador de fallos consecutivos
            consecutive_failures = 0
                
            # Extraer ofertas de trabajo (prueba varios selectores)
            job_cards = soup.select('div.base-card.relative, div.job-search-card, li.jobs-search-results__list-item')
            if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron más ofertas en página {current_page}")
                break
                
            logger.info(f"[{self.source_name}] Se encontraron {len(job_cards)} ofertas en página {current_page}")
            
            # Procesar cada tarjeta de trabajo
            page_jobs = []
            for card in job_cards:
                try:
                    job = self._extract_job_details(card)
                    
                    # Asegurarse de que tengamos datos mínimos
                    if job.get('titulo') and job.get('url'):
                        # Opcionalmente procesar páginas de detalle
                        if process_detail_pages and job.get('url'):
                            job = self._process_job_detail_page(job['url'], job)
                        
                        page_jobs.append(job)
                        self.stats['jobs_found'] += 1
                    
                except Exception as e:
                    logger.error(f"[{self.source_name}] Error procesando oferta: {e}")
                    continue
            
            # Verificar si encontramos ofertas en esta página
            if page_jobs:
                all_job_listings.extend(page_jobs)
                logger.info(f"[{self.source_name}] Añadidas {len(page_jobs)} ofertas de la página {current_page}")
            else:
                logger.warning(f"[{self.source_name}] No se pudieron extraer ofertas válidas de la página {current_page}")
                consecutive_failures += 1
            
            # Verificar si llegamos al límite de fallos o si no hay más páginas
            if consecutive_failures >= 2:
                logger.warning(f"[{self.source_name}] Terminando búsqueda por fallos consecutivos.")
                break
                
            current_page += 1
            
        # Mostrar estadísticas de ejecución
        logger.info(f"[{self.source_name}] Proceso finalizado. Estadísticas: {json.dumps(self.stats)}")
        logger.info(f"[{self.source_name}] Se encontraron {len(all_job_listings)} ofertas en total.")
        return all_job_listings


# Para compatibilidad con el código existente
class LinkedInScraper(LinkedInScraperImproved):
    """Clase de compatibilidad para el scraper mejorado"""
    pass


# Para pruebas directas de este scraper
if __name__ == "__main__":
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint
    
    # Configurar logging
    setup_logging()
    
    # Intentar usar el cliente HTTP mejorado si está disponible
    try:
        from src.utils.http_client_improved import ImprovedHTTPClient
        http_client = ImprovedHTTPClient()
        print("Usando cliente HTTP mejorado")
    except ImportError:
        http_client = HTTPClient()
        print("Usando cliente HTTP estándar")
    
    # Configuración para el scraper
    config = {
        'enabled': True,
        'base_url': 'https://www.linkedin.com/jobs/search/',
        'request_delay_seconds': 3.0,
        'max_retries': 3
    }
    
    # Crear instancia del scraper
    scraper = LinkedInScraperImproved(http_client=http_client, config=config)
    
    # Parámetros de búsqueda para probar
    search_params = {
        'keywords': ['data scientist', 'python', 'análisis de datos'],
        'location': 'Remote',
        'process_detail_pages': True  # Activar obtención de detalles
    }
    
    print(f"\n--- Iniciando prueba de {scraper.source_name} (versión mejorada) ---")
    print(f"Buscando trabajos con: {search_params}")
    
    try:
        # Ejecutar búsqueda
        ofertas = scraper.fetch_jobs(search_params)
        
        # Mostrar resultados
        print(f"\n--- Se encontraron {len(ofertas)} ofertas ---")
        
        if ofertas:
            print("\nPrimera oferta encontrada:")
            pprint.pprint(ofertas[0])
            
            if len(ofertas) > 1:
                print("\nSegunda oferta encontrada:")
                pprint.pprint(ofertas[1])
            
            print("\nÚltima oferta encontrada:")
            pprint.pprint(ofertas[-1])
            
            print(f"\nEstadísticas: {scraper.stats}")
            
    except Exception as e:
        print(f"Error durante la ejecución: {e}")
    finally:
        # Cerrar cliente HTTP
        http_client.close()
        print("\n--- Prueba finalizada ---")
