# -*- coding: utf-8 -*-
# /src/scrapers/linkedin_scraper.py

"""
Scraper para LinkedIn Jobs, enfocado en ciencia de datos, análisis de datos e ingeniería de datos.
Este scraper recupera ofertas de trabajo de LinkedIn utilizando filtros específicos y manejando la paginación.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus, urljoin
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
MAX_PAGES_TO_SCRAPE_LINKEDIN = 10  # Aumentamos para obtener más resultados, pero con cuidado

class LinkedInScraper(BaseScraper):
    """
    Scraper para LinkedIn Jobs que extrae ofertas de trabajo especializadas en datos.
    """
      def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="linkedin", http_client=http_client, config=config)
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
        
        # Headers personalizados para evitar bloqueos
        self.custom_headers = {
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
        
        # Configuración para control de frecuencia y reintentos
        self.request_delay = config.get('request_delay_seconds', 2.5) if config else 2.5
        self.max_retries = config.get('max_retries', 3) if config else 3
        self.error_count = 0
        self.success_count = 0    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
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
        
        # Intentar con nuestro helper general de fechas
        return process_date(date_text)

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Método principal que obtiene ofertas de trabajo de LinkedIn en base a los parámetros de búsqueda.
        
        Args:
            search_params: Diccionario con parámetros de búsqueda (keywords, location)
            
        Returns:
            Lista de ofertas de trabajo normalizadas
        """
        logger.info(f"[{self.source_name}] Iniciando búsqueda con parámetros: {search_params}")
        all_job_listings = []
        
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', '')
        
        # Limitar el número de keywords para evitar sobrecarga
        if len(keywords) > 3:
            data_keywords = [kw for kw in keywords if any(term in kw.lower() for term in 
                                                         ['data', 'datos', 'analytics', 'análisis', 
                                                          'scientist', 'machine learning', 'python', 'sql'])]
            if data_keywords:
                keywords = data_keywords[:3]
            else:
                keywords = keywords[:3]
            
        current_page = 1
        
        while current_page <= MAX_PAGES_TO_SCRAPE_LINKEDIN:
            logger.info(f"[{self.source_name}] Procesando página {current_page}...")
            
            url = self._build_search_url(keywords, location, current_page)
            if not url:
                logger.error(f"[{self.source_name}] Error construyendo URL para página {current_page}")
                break
                
            # Añadir pequeño delay para evitar bloqueos
            time.sleep(random.uniform(2, 4))
            
            html_content = self._fetch_html(url, headers=self.custom_headers)
            if not html_content:
                logger.warning(f"[{self.source_name}] No se pudo obtener HTML de página {current_page}")
                break
                
            soup = self._parse_html(html_content)
            if not soup:
                logger.warning(f"[{self.source_name}] No se pudo parsear HTML de página {current_page}")
                break
                
            # Extraer ofertas de trabajo
            job_cards = soup.select('div.base-card.relative')
            if not job_cards:
                logger.info(f"[{self.source_name}] No se encontraron más ofertas en página {current_page}")
                break
                
            logger.info(f"[{self.source_name}] Se encontraron {len(job_cards)} ofertas en página {current_page}")
            
            # Procesar cada tarjeta de trabajo
            for card in job_cards:
                try:
                    job = self.get_standard_job_dict()
                    
                    # Extraer título
                    title_elem = card.select_one('h3.base-search-card__title')
                    job['titulo'] = self._safe_get_text(title_elem)
                    
                    # Extraer empresa
                    company_elem = card.select_one('h4.base-search-card__subtitle')
                    job['empresa'] = self._safe_get_text(company_elem)
                    
                    # Extraer ubicación
                    location_elem = card.select_one('span.job-search-card__location')
                    job['ubicacion'] = self._safe_get_text(location_elem)
                    
                    # Extraer URL
                    url_elem = card.select_one('a.base-card__full-link')
                    job_url = self._safe_get_attribute(url_elem, 'href')
                    if job_url:
                        # Limpiar URL (LinkedIn a veces añade parámetros de tracking)
                        job_url = job_url.split('?')[0]
                        job['url'] = job_url
                    
                    # Extraer fecha
                    date_elem = card.select_one('time.job-search-card__listdate')
                    date_text = self._safe_get_attribute(date_elem, 'datetime')
                    if date_text:
                        job['fecha_publicacion'] = date_text[:10]  # YYYY-MM-DD
                    else:
                        date_text = self._safe_get_text(card.select_one('time, span.job-search-card__listdate'))
                        job['fecha_publicacion'] = self._parse_linkedin_date(date_text)
                    
                    # Extraer descripción corta (si está disponible)
                    desc_elem = card.select_one('p.base-card__metadata')
                    short_desc = self._safe_get_text(desc_elem)
                    if short_desc:
                        job['descripcion'] = short_desc
                    
                    # Extraer etiquetas o características adicionales
                    tags_elems = card.select('li.base-search-card__metadata-item')
                    tags = [self._safe_get_text(tag) for tag in tags_elems if tag]
                    if tags:
                        job['descripcion'] = (job['descripcion'] or '') + f"\nCaracterísticas: {', '.join(tags)}"
                    
                    # Asegurarse de que tengamos datos mínimos
                    if job['titulo'] and job['url']:
                        job['fuente'] = self.source_name
                        all_job_listings.append(job)
                        
                except Exception as e:
                    logger.error(f"[{self.source_name}] Error procesando oferta: {e}")
                    continue
                    
            current_page += 1
            
        logger.info(f"[{self.source_name}] Proceso finalizado. Se encontraron {len(all_job_listings)} ofertas en total.")
        return all_job_listings

# Para pruebas directas de este scraper
if __name__ == "__main__":
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint
    
    # Configurar logging
    setup_logging()
    
    # Crear cliente HTTP
    http_client = HTTPClient()
    
    # Configuración para el scraper
    config = {
        'enabled': True,
        'base_url': 'https://www.linkedin.com/jobs/search/'
    }
    
    # Crear instancia del scraper
    scraper = LinkedInScraper(http_client=http_client, config=config)
    
    # Parámetros de búsqueda para probar
    search_params = {
        'keywords': ['data scientist', 'python', 'análisis de datos'],
        'location': 'Remote'
    }
    
    print(f"\n--- Iniciando prueba de {scraper.source_name} ---")
    print(f"Buscando trabajos con: {search_params}")
    
    try:
        # Ejecutar búsqueda
        ofertas = scraper.fetch_jobs(search_params)
        
        # Mostrar resultados
        print(f"\n--- Se encontraron {len(ofertas)} ofertas ---")
        
        if ofertas:
            print("\nPrimera oferta encontrada:")
            pprint.pprint(ofertas[0])
            
            print("\nÚltima oferta encontrada:")
            pprint.pprint(ofertas[-1])
            
    except Exception as e:
        print(f"Error durante la ejecución: {e}")
    finally:
        # Cerrar cliente HTTP
        http_client.close()
        print("\n--- Prueba finalizada ---")
