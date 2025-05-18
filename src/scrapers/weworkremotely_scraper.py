# -*- coding: utf-8 -*-
# /src/scrapers/weworkremotely_scraper.py

"""
Scraper para WeWorkRemotely.com, una plataforma especializada en trabajos remotos.
Altamente reconocida por su calidad de ofertas de trabajo para profesionales.
"""

import re
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper
from src.utils.helpers import normalize_text, safe_url_join, process_date

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
]

class WeWorkRemotelyScraper(BaseScraper):
    """
    Scraper para WeWorkRemotely.com - Plataforma de trabajo remoto premium.
    
    Características:
    - Enfocada en trabajo remoto de alta calidad
    - Empresas verificadas
    - Categorías definidas para distintos sectores
    """
    
    def __init__(self, http_client=None, config=None):
        """Inicializa el scraper con configuración específica para WeWorkRemotely."""
        super().__init__(http_client, config)
        self.source_name = "WeWorkRemotely"
        self.base_url = config.get('base_url', 'https://weworkremotely.com/')
        # Headers personalizados
        self.custom_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        # Mapeo de categorías populares
        self.categories = {
            'programming': 'remote-programming-jobs',
            'development': 'remote-development-jobs',
            'design': 'remote-design-jobs',
            'marketing': 'remote-marketing-jobs',
            'management': 'remote-management-jobs',
            'sales': 'remote-sales-jobs',
            'customer-support': 'remote-customer-support-jobs',
            'finance': 'remote-finance-jobs',
            'product': 'remote-product-jobs',
        }
    
    def _build_search_url(self, keyword: str, location: Optional[str] = None, page: int = 1) -> str:
        """
        Construye la URL de búsqueda para WeWorkRemotely.
        
        Args:
            keyword: Palabra clave de búsqueda (tecnología, puesto, etc.)
            location: Ubicación (no aplica para WWR que es 100% remoto)
            page: Número de página (WWR usa URL diferentes para cada página)
            
        Returns:
            URL completa para realizar la búsqueda
        """
        # Normalizar keyword y convertir espacios a '+'
        keyword = normalize_text(keyword, remove_accents=True, lowercase=True)
        
        # Primero verificar si la keyword coincide con alguna categoría predefinida
        for category_key, category_url in self.categories.items():
            if category_key in keyword:
                return f"{self.base_url}{category_url}"
        
        # Si no coincide con categoría, usamos búsqueda general
        keyword_url = keyword.replace(' ', '+')
        search_url = f"{self.base_url}remote-jobs-search?term={keyword_url}"
        
        # WWR no tiene paginación estándar con página=X
        # Ignoramos el parámetro de página
        
        return search_url
    
    def _fetch_html_with_retry(self, url, max_retries=3):
        """
        Obtiene el contenido HTML de una URL con reintentos y rotación de User-Agent.
        
        Args:
            url: URL a la que se hará la petición
            max_retries: Número máximo de reintentos
            
        Returns:
            Contenido HTML de la respuesta o None si falla
        """
        for attempt in range(max_retries):
            headers = {
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            try:
                response = self.http_client.get(url, headers=headers)
                if response and response.text:
                    return response.text
            except Exception as e:
                logger.warning(f"[{self.source_name}] Reintento {attempt+1} fallido para {url}: {e}")
        logger.error(f"[{self.source_name}] Fallaron todos los reintentos para {url}")
        return None

    def search_jobs(self, keyword: str, location: Optional[str] = None, max_pages: int = 1) -> List[Dict[str, Any]]:
        """
        Busca trabajos en WeWorkRemotely para la keyword dada.
        
        Args:
            keyword: Palabra clave para buscar
            location: Ubicación (no aplica para WWR)
            max_pages: Número máximo de páginas (WWR carga todo en una página)
            
        Returns:
            Lista de ofertas de trabajo encontradas
        """
        all_job_listings = []
        
        search_url = self._build_search_url(keyword, location)
        logger.info(f"Buscando ofertas en {self.source_name}: {search_url}")
        
        try:
            html_content = self._fetch_html_with_retry(search_url)
            if not html_content:
                logger.error(f"[{self.source_name}] No se pudo obtener HTML tras reintentos para {search_url}")
                return []
            
            # Parsear las ofertas
            page_listings = self._parse_job_listings(html_content, search_url)
            all_job_listings.extend(page_listings)
            
            logger.info(f"Se encontraron {len(page_listings)} ofertas en {self.source_name}")
            
        except Exception as e:
            logger.error(f"Error al buscar en {self.source_name}: {e}")
        
        return all_job_listings
    
    def _parse_job_listings(self, html_content: str, base_search_url: str) -> List[Dict[str, Any]]:
        """
        Extrae las ofertas de trabajo del HTML de la página de resultados.
        
        Args:
            html_content: Contenido HTML de la página de resultados
            base_search_url: URL base de la búsqueda para resolver URLs relativas
            
        Returns:
            Lista de diccionarios con la información de las ofertas de trabajo
        """
        job_listings = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # En WWR, los trabajos están dentro de secciones con clase "jobs"
        jobs_sections = soup.select('section.jobs')
        
        # Iterar por cada sección
        for section in jobs_sections:
            # Obtener la categoría (aparece en el encabezado de la sección)
            category_header = section.select_one('h2, h3, .section-title')
            category_name = category_header.text.strip() if category_header else "General"
            
            # Encontrar todos los artículos de trabajo en esta sección
            job_items = section.select('li.feature')
            if not job_items:
                job_items = section.select('li:not(.view-all)')
            
            logger.debug(f"Encontrados {len(job_items)} items en {category_name} en WeWorkRemotely")
            
            # Procesar cada trabajo
            for job_item in job_items:
                try:
                    # Ignorar elementos que no son trabajos
                    if 'view-all' in job_item.get('class', []):
                        continue
                    
                    # Extraer URL del trabajo
                    job_link = job_item.select_one('a')
                    if not job_link:
                        continue
                        
                    relative_url = job_link.get('href')
                    job_url = safe_url_join('https://weworkremotely.com', relative_url)
                    
                    # Extraer título
                    title_elem = job_item.select_one('.title')
                    title = title_elem.text.strip() if title_elem else ""
                    
                    # Extraer empresa
                    company_elem = job_item.select_one('.company')
                    company = company_elem.text.strip() if company_elem else ""
                    
                    # Extraer ubicación (WWR incluye detalles de regiones permitidas)
                    region_elem = job_item.select_one('.region')
                    region = region_elem.text.strip() if region_elem else "Worldwide"
                    
                    # Extraer tiempo de publicación
                    date = None
                    time_elem = job_item.select_one('.date')
                    if time_elem:
                        date_text = time_elem.text.strip()
                        date = self._parse_date(date_text)
                    
                    # Extraer etiquetas
                    tags_elems = job_item.select('.tags span')
                    tags = [tag.text.strip() for tag in tags_elems] if tags_elems else []
                    tags_text = ", ".join(tags) if tags else ""
                    
                    # Crear el objeto de oferta
                    job = {
                        'titulo': title,
                        'empresa': company,
                        'ubicacion': f"Remote - {region}",
                        'url': job_url,
                        'fecha_publicacion': date,
                        'descripcion': f"Categoría: {category_name} | Tags: {tags_text}",
                        'salario': None,  # WWR no muestra salarios en la vista de lista
                        'fuente': self.source_name
                    }
                    
                    job_listings.append(job)
                    
                except Exception as e:
                    logger.error(f"Error al parsear oferta en WeWorkRemotely: {e}")
                    continue
                    
        return job_listings
    
    def _parse_date(self, date_string: Optional[str]) -> Optional[str]:
        """
        Parsea las fechas de WeWorkRemotely al formato YYYY-MM-DD.
        
        Args:
            date_string: String de fecha (ej: "2d ago", "5h ago", "Mar 24", etc.)
            
        Returns:
            Fecha en formato YYYY-MM-DD o None si no se puede parsear
        """
        if not date_string:
            return None
            
        date_string = date_string.lower().strip()
        today = datetime.now().date()
        
        # Para "XD ago" (días)
        day_pattern = re.search(r'(\d+)d', date_string)
        if day_pattern:
            days = int(day_pattern.group(1))
            return (today - timedelta(days=days)).strftime('%Y-%m-%d')
            
        # Para "Xh ago" (horas)
        hour_pattern = re.search(r'(\d+)h', date_string)
        if hour_pattern:
            return today.strftime('%Y-%m-%d')  # mismo día
            
        # Para fechas del tipo "MMM DD" ("Mar 24")
        month_day_pattern = re.search(r'([a-z]{3})\s+(\d{1,2})', date_string)
        if month_day_pattern:
            month_str = month_day_pattern.group(1)
            day = int(month_day_pattern.group(2))
            
            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            
            month = month_map.get(month_str.lower(), None)
            if month:
                year = today.year
                # Si la fecha sería en el futuro, probablemente es del año pasado
                if month > today.month or (month == today.month and day > today.day):
                    year -= 1
                    
                return f"{year}-{month:02d}-{day:02d}"
        
        # Para "today", "yesterday"
        if 'today' in date_string:
            return today.strftime('%Y-%m-%d')
            
        if 'yesterday' in date_string:
            return (today - timedelta(days=1)).strftime('%Y-%m-%d')
            
        # Para otros formatos, usar el helper general
        return process_date(date_string)
        
    def _has_next_page(self, html_content: str, current_page: int) -> bool:
        """
        WeWorkRemotely muestra todos los resultados en una página.
        
        Args:
            html_content: Contenido HTML de la página actual
            current_page: Número de página actual
            
        Returns:
            False (WeWorkRemotely no tiene paginación)
        """
        return False