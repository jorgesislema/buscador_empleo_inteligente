# -*- coding: utf-8 -*-
# /src/scrapers/remoteok_scraper.py

"""
Scraper para RemoteOK.com, una plataforma especializada en trabajos remotos.
Enfocada principalmente en tecnología y desarrollo de software.
"""

import re
import json
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

class RemoteOkScraper(BaseScraper):
    """
    Scraper para RemoteOK.com - Board de trabajos 100% remotos.
    
    Características:
    - Todos los empleos son 100% remotos
    - Fuerte enfoque en desarrollo, diseño y marketing digital
    - API JSON disponible (pero usamos scraping para mantener uniformidad)
    """
    
    def __init__(self, http_client=None, config=None):
        """Inicializa el scraper con configuración específica para RemoteOK."""
        super().__init__(http_client, config)
        self.source_name = "RemoteOK"
        self.base_url = config.get('base_url', 'https://remoteok.com/')
        # Headers especiales para evitar bloqueos
        self.custom_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
    
    def _build_search_url(self, keyword: str, location: Optional[str] = None, page: int = 1) -> str:
        """
        Construye la URL de búsqueda para RemoteOK.
        
        Args:
            keyword: Palabra clave de búsqueda (tecnología, puesto, etc.)
            location: Ubicación (no aplica para RemoteOK que es 100% remoto)
            page: Número de página (RemoteOK no usa paginación tradicional)
            
        Returns:
            URL completa para realizar la búsqueda
        """
        # Normalizar keyword y convertir espacios a '+'
        keyword = normalize_text(keyword, remove_accents=True, lowercase=True)
        keyword_url = keyword.replace(' ', '+')
        
        # URL de búsqueda
        search_url = f"{self.base_url}remote-{keyword_url}-jobs"
        
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
        Busca trabajos en RemoteOK para la keyword dada.
        RemoteOK no tiene paginación tradicional, carga todos los resultados en una página.
        
        Args:
            keyword: Palabra clave para buscar
            location: Ubicación (no aplica para RemoteOK)
            max_pages: Ignorado para RemoteOK
            
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
            
            # RemoteOK tiene una API JSON oculta, intentamos usarla primero
            json_jobs = self._try_json_api(html_content)
            if json_jobs:
                all_job_listings.extend(json_jobs)
                logger.info(f"Se encontraron {len(json_jobs)} ofertas usando API JSON")
            else:
                # Si falla, usar scraping tradicional
                page_listings = self._parse_job_listings(html_content, search_url)
                all_job_listings.extend(page_listings)
                logger.info(f"Se encontraron {len(page_listings)} ofertas usando scraping HTML")
            
        except Exception as e:
            logger.error(f"Error al buscar en {self.source_name}: {e}")
        
        return all_job_listings
    
    def _try_json_api(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Intenta obtener los trabajos desde el script JSON que RemoteOK incluye en su HTML.
        
        Args:
            html_content: Contenido HTML de la página de resultados
            
        Returns:
            Lista de ofertas de trabajo o lista vacía si no se puede extraer
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # RemoteOK inyecta un script con datos JSON
            script_tag = soup.find('script', id='job-list')
            if not script_tag:
                return []
                
            # Extraer el JSON
            json_text = script_tag.string.strip()
            if not json_text:
                return []
                
            # Parsear el JSON
            job_data = json.loads(json_text)
            
            # Convertir al formato estándar
            job_listings = []
            
            for job in job_data:
                try:
                    # Saltar anuncios o entradas no válidas
                    if 'id' not in job or job.get('legal', False):
                        continue
                        
                    # Extraer información relevante
                    job_id = job.get('id')
                    company = job.get('company', '')
                    position = job.get('position', '')
                    description = job.get('description', '')
                    tags = job.get('tags', [])
                    location = job.get('location', 'Remote')
                    salary = job.get('salary', '')
                    
                    # RemoteOK usa epoch unix timestamp
                    date = None
                    if 'date' in job:
                        try:
                            date_obj = datetime.fromtimestamp(int(job['date']))
                            date = date_obj.strftime('%Y-%m-%d')
                        except:
                            pass
                    
                    # URL del trabajo
                    url = f"https://remoteok.com/remote-jobs/{job_id}"
                    
                    # Crear el objeto de oferta
                    job_listing = {
                        'titulo': position,
                        'empresa': company,
                        'ubicacion': f"Remote - {location}",
                        'url': url,
                        'fecha_publicacion': date,
                        'descripcion': description[:250] + "..." if description else "",
                        'salario': salary if salary else None,
                        'fuente': self.source_name
                    }
                    
                    job_listings.append(job_listing)
                    
                except Exception as e:
                    logger.error(f"Error al procesar trabajo JSON en RemoteOK: {e}")
                    continue
                    
            return job_listings
            
        except Exception as e:
            logger.error(f"Error al extraer JSON de RemoteOK: {e}")
            return []
    
    def _parse_job_listings(self, html_content: str, base_search_url: str) -> List[Dict[str, Any]]:
        """
        Extrae las ofertas de trabajo del HTML mediante scraping tradicional.
        Usado como fallback si la API JSON no funciona.
        
        Args:
            html_content: Contenido HTML de la página de resultados
            base_search_url: URL base de la búsqueda para resolver URLs relativas
            
        Returns:
            Lista de diccionarios con la información de las ofertas de trabajo
        """
        job_listings = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # RemoteOK usa tr con data-id para sus trabajos
        job_items = soup.select('tr[data-id]')
        
        logger.debug(f"Encontrados {len(job_items)} items en RemoteOK mediante scraping HTML")
        
        for job_item in job_items:
            try:
                # Verificar si es un trabajo real (no un anuncio)
                if 'data-id' not in job_item.attrs:
                    continue
                
                job_id = job_item.get('data-id')
                
                # Verificar si es un anuncio
                if 'data-adblock' in job_item.attrs:
                    continue
                
                # Extraer título
                title_elem = job_item.select_one('h2')
                title = title_elem.text.strip() if title_elem else ""
                
                # Extraer empresa
                company_elem = job_item.select_one('.company')
                company = company_elem.text.strip() if company_elem else ""
                
                # Extraer tags/habilidades
                tags_elems = job_item.select('.tag')
                tags = [tag.text.strip() for tag in tags_elems] if tags_elems else []
                tags_text = ", ".join(tags) if tags else ""
                
                # Extraer ubicación
                location_elem = job_item.select_one('.location')
                location = location_elem.text.strip() if location_elem else "Remote"
                
                # Extraer tiempo de publicación
                time_elem = job_item.select_one('time')
                date = None
                if time_elem:
                    date_value = time_elem.get('datetime')
                    if date_value:
                        try:
                            date_obj = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                            date = date_obj.strftime('%Y-%m-%d')
                        except:
                            pass
                
                # Extraer salario si está disponible
                salary_elem = job_item.select_one('.salary')
                salary = salary_elem.text.strip() if salary_elem else None
                
                # Construir URL del trabajo
                job_url = f"https://remoteok.com/remote-jobs/{job_id}"
                
                # Crear el objeto de oferta
                job = {
                    'titulo': title,
                    'empresa': company,
                    'ubicacion': f"Remote - {location}",
                    'url': job_url,
                    'fecha_publicacion': date,
                    'descripcion': f"Habilidades: {tags_text}",
                    'salario': salary,
                    'fuente': self.source_name
                }
                
                job_listings.append(job)
                
            except Exception as e:
                logger.error(f"Error al parsear oferta en RemoteOK: {e}")
                continue
                
        return job_listings
        
    def _has_next_page(self, html_content: str, current_page: int) -> bool:
        """
        RemoteOK no tiene paginación tradicional, siempre devuelve False.
        
        Args:
            html_content: Contenido HTML de la página actual
            current_page: Número de página actual
            
        Returns:
            False (RemoteOK no tiene paginación)
        """
        return False