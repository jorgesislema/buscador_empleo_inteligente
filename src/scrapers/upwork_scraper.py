# -*- coding: utf-8 -*-
# /src/scrapers/upwork_scraper.py

"""
Scraper para Upwork.com, una de las plataformas de freelance más grandes del mundo.
Enfocada en trabajos freelance en tecnología, diseño, redacción, marketing, etc.
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper
from src.utils.helpers import normalize_text, safe_url_join, process_date

logger = logging.getLogger(__name__)

class UpworkScraper(BaseScraper):
    """
    Scraper para Upwork.com - Plataforma líder en trabajos freelance.
    
    Características:
    - Proyectos y contratos freelance a nivel global
    - Ideal para desarrolladores, diseñadores, escritores y especialistas en marketing
    - Proyectos de corto, medio y largo plazo
    """
    
    def __init__(self, http_client=None, config=None):
        """Inicializa el scraper con configuración específica para Upwork."""
        super().__init__(http_client, config)
        self.source_name = "Upwork"
        self.base_url = config.get('base_url', 'https://www.upwork.com/freelance-jobs/')
        # Headers personalizados para evitar bloqueos
        self.custom_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    def _build_search_url(self, keyword: str, location: Optional[str] = None, page: int = 1) -> str:
        """
        Construye la URL de búsqueda para Upwork.
        
        Args:
            keyword: Palabra clave de búsqueda (tecnología, puesto, etc.)
            location: Ubicación (no muy relevante para Upwork que es global)
            page: Número de página
            
        Returns:
            URL completa para realizar la búsqueda
        """
        # Normalizar keyword y convertir espacios a guiones
        keyword = normalize_text(keyword, remove_accents=True, lowercase=True)
        keyword_slug = keyword.replace(' ', '-')
        
        # URL base de búsqueda
        search_url = f"{self.base_url}{keyword_slug}/"
        
        # Añadir paginación
        if page > 1:
            search_url += f"?page={page}"
            
        return search_url
    
    def search_jobs(self, keyword: str, location: Optional[str] = None, max_pages: int = 5) -> List[Dict[str, Any]]:
        """
        Busca trabajos en Upwork para la keyword y opcionalmente la ubicación.
        
        Args:
            keyword: Palabra clave para buscar
            location: Ubicación (opcional)
            max_pages: Número máximo de páginas a procesar
            
        Returns:
            Lista de ofertas de trabajo encontradas
        """
        all_job_listings = []
        
        for page in range(1, max_pages + 1):
            search_url = self._build_search_url(keyword, location, page)
            logger.info(f"Buscando ofertas en {self.source_name} - Página {page}: {search_url}")
            
            try:
                # Usar headers personalizados para evitar bloqueos
                response = self.http_client.get(search_url, headers=self.custom_headers)
                html_content = response.text
                
                # Parsear las ofertas de esta página
                page_listings = self._parse_job_listings(html_content, search_url)
                all_job_listings.extend(page_listings)
                
                logger.info(f"Se encontraron {len(page_listings)} ofertas en página {page}")
                
                # Verificar si hay más páginas
                if not self._has_next_page(html_content, page):
                    logger.info(f"No hay más páginas en {self.source_name} para esta búsqueda")
                    break
                    
                # Esperar entre peticiones para no sobrecargar
                self.http_client.delay_request()
                
            except Exception as e:
                logger.error(f"Error al buscar en {self.source_name} - Página {page}: {e}")
                break
        
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
        
        # Upwork tiene varias posibles estructuras HTML
        job_items = soup.select('section.air3-card.job-tile')
        if not job_items:
            # Probar con otro selector
            job_items = soup.select('.job-tile')
            if not job_items:
                # Un último intento
                job_items = soup.select('[data-job-tile]')
        
        logger.debug(f"Encontrados {len(job_items)} items en Upwork")
        
        for job_item in job_items:
            try:
                # Extraer URL del trabajo
                job_link = job_item.select_one('a[href*="/job/"]') or job_item.select_one('a.job-title-link')
                if not job_link:
                    continue
                    
                relative_url = job_link.get('href')
                job_url = safe_url_join('https://www.upwork.com', relative_url)
                
                # Extraer título
                title_elem = job_link or job_item.select_one('.job-title')
                title = title_elem.text.strip() if title_elem else ""
                
                # Extraer presupuesto/precio
                budget_elem = job_item.select_one('.js-budget, .js-hourly-rate, [data-test="budget"], .job-tile-budget')
                budget = budget_elem.text.strip() if budget_elem else "No especificado"
                
                # Extraer descripción
                desc_elem = job_item.select_one('.job-description-text, [data-test="job-description"]')
                description = desc_elem.text.strip() if desc_elem else ""
                
                # Extraer habilidades/tags
                skills_elems = job_item.select('.job-skills .up-skill-badge')
                skills = [skill.text.strip() for skill in skills_elems] if skills_elems else []
                skills_text = ", ".join(skills) if skills else ""
                
                # Extraer tiempo de publicación
                time_elem = job_item.select_one('.job-created-time, [data-test="posted-on"]')
                posted_time = time_elem.text.strip() if time_elem else ""
                date = self._parse_date(posted_time)
                
                # Extraer nivel requerido (Entry/Intermediate/Expert)
                level_elem = job_item.select_one('[data-test="contractor-tier"]')
                level = level_elem.text.strip() if level_elem else ""
                
                # Crear el objeto de oferta
                job = {
                    'titulo': title,
                    'empresa': "Freelance en Upwork",
                    'ubicacion': "Remote - Global",
                    'url': job_url,
                    'fecha_publicacion': date,
                    'descripcion': f"{description[:250]}... | Habilidades: {skills_text} | Nivel: {level}",
                    'salario': budget,
                    'fuente': self.source_name
                }
                
                job_listings.append(job)
                
            except Exception as e:
                logger.error(f"Error al parsear oferta en Upwork: {e}")
                continue
                
        return job_listings
    
    def _parse_date(self, date_string: Optional[str]) -> Optional[str]:
        """
        Parsea la fecha de publicación de Upwork al formato YYYY-MM-DD.
        
        Args:
            date_string: String de fecha (ej: "Posted 2 hours ago", "Posted 3 days ago", etc.)
            
        Returns:
            Fecha en formato YYYY-MM-DD o None si no se puede parsear
        """
        if not date_string:
            return None
            
        date_string = date_string.lower().strip()
        today = datetime.now().date()
        
        # Patterns comunes de Upwork
        hour_pattern = re.search(r'(\d+)\s*(?:hour|hr)s?', date_string)
        if hour_pattern:
            hours = int(hour_pattern.group(1))
            return today.strftime('%Y-%m-%d')  # Mismo día
            
        day_pattern = re.search(r'(\d+)\s*day', date_string)
        if day_pattern:
            days = int(day_pattern.group(1))
            return (today - timedelta(days=days)).strftime('%Y-%m-%d')
            
        week_pattern = re.search(r'(\d+)\s*week', date_string)
        if week_pattern:
            weeks = int(week_pattern.group(1))
            return (today - timedelta(weeks=weeks)).strftime('%Y-%m-%d')
            
        month_pattern = re.search(r'(\d+)\s*month', date_string)
        if month_pattern:
            months = int(month_pattern.group(1))
            return (today - timedelta(days=months*30)).strftime('%Y-%m-%d')
        
        # Verificar textos específicos
        if 'today' in date_string or 'just now' in date_string:
            return today.strftime('%Y-%m-%d')
            
        if 'yesterday' in date_string:
            return (today - timedelta(days=1)).strftime('%Y-%m-%d')
            
        # Para otros formatos, usar el helper general
        return process_date(date_string)
        
    def _has_next_page(self, html_content: str, current_page: int) -> bool:
        """
        Determina si hay una página siguiente de resultados.
        
        Args:
            html_content: Contenido HTML de la página actual
            current_page: Número de página actual
            
        Returns:
            True si hay más páginas, False si no
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Buscar enlaces de paginación
        pagination = soup.select('.pagination button, .pagination a, [data-test="pagination-next"]')
        if not pagination:
            return False
            
        # Buscar el botón "Next" o similar
        for page_link in pagination:
            text = page_link.text.strip().lower()
            if 'next' in text or '→' in text or '>' in text:
                # Verificar si está deshabilitado
                if 'disabled' in page_link.get('class', []) or page_link.get('disabled') == 'disabled':
                    return False
                return True
                
        return False