# -*- coding: utf-8 -*-
# /src/scrapers/wellfound_scraper.py

"""
Scraper para Wellfound (anteriormente AngelList), enfocado en empleos de startups
en ciencia de datos, análisis de datos e ingeniería de datos.
"""

import logging
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus, urljoin
import time
import random

from src.scrapers.base_scraper import BaseScraper
from src.utils.http_client import HTTPClient
from src.utils.helpers import process_date

logger = logging.getLogger(__name__)
MAX_PAGES_TO_SCRAPE_WELLFOUND = 5  # Limitamos para evitar bloqueos

class WellfoundScraper(BaseScraper):
    """
    Scraper para Wellfound (AngelList) para extraer ofertas de trabajo en startups.
    """
    
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name="wellfound", http_client=http_client, config=config)
        if not self.base_url:
            self.base_url = "https://wellfound.com/jobs"
            logger.warning(f"[{self.source_name}] 'base_url' no encontrada. Usando default: {self.base_url}")
        
        # Headers personalizados para evitar bloqueos
        self.custom_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://wellfound.com/',
            'sec-ch-ua': '"Not?A_Brand";v="8", "Chromium";v="113"',
            'sec-ch-ua-platform': '"Windows"',
        }

    def _build_search_url(self, keywords: List[str], location: str, page: int = 1) -> Optional[str]:
        """
        Construye la URL para buscar trabajos en Wellfound en base a palabras clave y ubicación.
        
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
            
        # Preparar keywords para Wellfound
        # Wellfound usa una estructura de URL específica para las búsquedas
        keyword_query = ""
        if keywords and len(keywords) > 0:
            # Priorizar términos de datos y tecnología
            data_terms = ["data", "datos", "scientist", "analysis", "analisis", "python", "machine learning", "engineer"]
            
            filtered_keywords = []
            # Primero buscar términos relacionados con datos
            for kw in keywords:
                if any(term in kw.lower() for term in data_terms):
                    filtered_keywords.append(kw)
                    if len(filtered_keywords) >= 2:  # Limitar a 2 términos
                        break
            
            # Si no hay términos de datos, usar los primeros 2 términos genéricos
            if not filtered_keywords and keywords:
                filtered_keywords = keywords[:2]
                
            keyword_query = quote_plus(" ".join(filtered_keywords))
        
        # Construir URL base 
        url = f"{self.base_url}"
        
        # Añadir filtros
        filters = []
        
        # Añadir keywords como filtro
        if keyword_query:
            filters.append(f"r={keyword_query}")
        
        # Procesar ubicación
        if location:
            if any(term in location.lower() for term in ['remote', 'remoto', 'teletrabajo']):
                filters.append("remote=true")
            else:
                filters.append(f"l={quote_plus(location)}")
        
        # Añadir filtros a la URL
        if filters:
            url += "?" + "&".join(filters)
        
        # Añadir paginación
        if page > 1:
            url += "&page=" if "?" in url else "?page="
            url += str(page)
        
        logger.debug(f"[{self.source_name}] URL de búsqueda construida: {url}")
        return url

    def _parse_wellfound_date(self, date_text: Optional[str]) -> Optional[str]:
        """
        Parsea el formato de fecha de Wellfound a formato ISO.
        
        Args:
            date_text: Texto de fecha (ej: "3 days ago", "Posted 1 week ago", etc.)
            
        Returns:
            Fecha en formato ISO YYYY-MM-DD o None si no se puede parsear
        """
        if not date_text:
            return None
            
        return process_date(date_text)

    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Método principal que obtiene ofertas de trabajo de Wellfound en base a los parámetros de búsqueda.
        
        Args:
            search_params: Diccionario con parámetros de búsqueda (keywords, location)
            
        Returns:
            Lista de ofertas de trabajo normalizadas
        """
        logger.info(f"[{self.source_name}] Iniciando búsqueda con parámetros: {search_params}")
        all_job_listings = []
        
        keywords = search_params.get('keywords', [])
        location = search_params.get('location', '')
        
        current_page = 1
        while current_page <= MAX_PAGES_TO_SCRAPE_WELLFOUND:
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
            
            # Intentar extraer datos del estado inicial incrustado en la página
            job_data = []
            script_tags = soup.select('script#__NEXT_DATA__')
            if script_tags and len(script_tags) > 0:
                try:
                    json_data = json.loads(script_tags[0].string)
                    # Navegar a través de la estructura del JSON para encontrar los trabajos
                    if 'props' in json_data and 'pageProps' in json_data['props']:
                        page_props = json_data['props']['pageProps']
                        if 'searchResult' in page_props and 'jobs' in page_props['searchResult']:
                            job_data = page_props['searchResult']['jobs']
                            logger.debug(f"[{self.source_name}] Encontrados {len(job_data)} trabajos en JSON incrustado")
                except Exception as e:
                    logger.error(f"[{self.source_name}] Error procesando JSON incrustado: {e}")
            
            if job_data:
                # Procesar datos extraídos del JSON
                for job_item in job_data:
                    try:
                        job = self.get_standard_job_dict()
                        
                        # Extraer título
                        job['titulo'] = job_item.get('title')
                        
                        # Extraer empresa
                        company = job_item.get('startup', {})
                        job['empresa'] = company.get('name') if company else None
                        
                        # Extraer ubicación
                        locations = job_item.get('locations', [])
                        if locations:
                            job['ubicacion'] = ", ".join([loc.get('name', '') for loc in locations if 'name' in loc])
                        
                        # Manejar trabajos remotos
                        if job_item.get('remote'):
                            job['ubicacion'] = f"Remote{' - ' + job['ubicacion'] if job['ubicacion'] else ''}"
                        
                        # Extraer URL
                        slug = job_item.get('slug')
                        if slug:
                            job['url'] = f"https://wellfound.com/jobs/{slug}"
                        
                        # Extraer fecha (convertir de timestamp si está disponible)
                        if 'publishedAt' in job_item:
                            try:
                                publish_date = datetime.fromtimestamp(job_item['publishedAt'])
                                job['fecha_publicacion'] = publish_date.strftime('%Y-%m-%d')
                            except:
                                pass
                        
                        # Extraer tags/skills
                        roles = job_item.get('roleTypes', [])
                        skills = job_item.get('skills', [])
                        
                        description_parts = []
                        
                        # Añadir descripción si existe
                        if 'description' in job_item and job_item['description']:
                            description_parts.append(job_item['description'])
                        
                        # Añadir roles
                        if roles:
                            role_names = [role.get('name', '') for role in roles if 'name' in role]
                            if role_names:
                                description_parts.append(f"Roles: {', '.join(role_names)}")
                        
                        # Añadir skills/tags
                        if skills:
                            skill_names = [skill.get('name', '') for skill in skills if 'name' in skill]
                            if skill_names:
                                description_parts.append(f"Skills: {', '.join(skill_names)}")
                        
                        # Añadir compensación si existe
                        compensation = job_item.get('compensation', {})
                        if compensation:
                            salary_min = compensation.get('min')
                            salary_max = compensation.get('max')
                            if salary_min and salary_max:
                                currency = compensation.get('currency', 'USD')
                                job['salario'] = f"{currency} {salary_min}-{salary_max}"
                                description_parts.append(f"Salary: {job['salario']}")
                        
                        # Unir todas las partes de la descripción
                        job['descripcion'] = "\n\n".join(description_parts)
                        
                        # Asegurarse de que tengamos datos mínimos
                        if job['titulo'] and job['url']:
                            job['fuente'] = self.source_name
                            all_job_listings.append(job)
                    
                    except Exception as e:
                        logger.error(f"[{self.source_name}] Error procesando oferta: {e}")
                        continue
            else:
                # Fallback: extraer manualmente de los elementos HTML
                job_cards = soup.select('div.job-list-item, div.job-listing-card')
                if not job_cards:
                    logger.info(f"[{self.source_name}] No se encontraron más ofertas en página {current_page}")
                    break
                
                logger.info(f"[{self.source_name}] Se encontraron {len(job_cards)} ofertas en página {current_page}")
                
                # Procesar cada tarjeta de trabajo
                for card in job_cards:
                    try:
                        job = self.get_standard_job_dict()
                        
                        # Extraer título
                        title_elem = card.select_one('a.job-title, h3.job-title')
                        job['titulo'] = self._safe_get_text(title_elem)
                        
                        # Extraer empresa
                        company_elem = card.select_one('a.startup-link, div.startup-name')
                        job['empresa'] = self._safe_get_text(company_elem)
                        
                        # Extraer ubicación
                        location_elem = card.select_one('div.location, span.location')
                        job['ubicacion'] = self._safe_get_text(location_elem)
                        
                        # Extraer URL
                        url_elem = card.select_one('a.job-title, a.job-listing-link')
                        job_url = self._safe_get_attribute(url_elem, 'href')
                        if job_url:
                            if not job_url.startswith('http'):
                                job_url = f"https://wellfound.com{job_url}"
                            job['url'] = job_url
                        
                        # Extraer fecha
                        date_elem = card.select_one('div.posted-date, span.posted-date')
                        date_text = self._safe_get_text(date_elem)
                        job['fecha_publicacion'] = self._parse_wellfound_date(date_text)
                        
                        # Extraer etiquetas/skills
                        tags_elems = card.select('div.role-tag, span.tag, span.skill-tag')
                        tags = [self._safe_get_text(tag) for tag in tags_elems if tag]
                        if tags:
                            job['descripcion'] = f"Skills/Tags: {', '.join(tags)}"
                        
                        # Extraer salario si está disponible
                        salary_elem = card.select_one('div.compensation, span.compensation')
                        if salary_elem:
                            job['salario'] = self._safe_get_text(salary_elem)
                            job['descripcion'] = (job['descripcion'] or '') + f"\nSalario: {job['salario']}"
                        
                        # Asegurarse de que tengamos datos mínimos
                        if job['titulo'] and job['url']:
                            job['fuente'] = self.source_name
                            all_job_listings.append(job)
                            
                    except Exception as e:
                        logger.error(f"[{self.source_name}] Error procesando oferta: {e}")
                        continue
            
            # Verificar si hay una página siguiente
            next_page = soup.select_one('a.next-page, a[rel="next"]')
            if not next_page:
                logger.info(f"[{self.source_name}] No se encontró botón de siguiente página")
                break
                
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
        'base_url': 'https://wellfound.com/jobs'
    }
    
    # Crear instancia del scraper
    scraper = WellfoundScraper(http_client=http_client, config=config)
    
    # Parámetros de búsqueda para probar
    search_params = {
        'keywords': ['data scientist', 'python', 'machine learning'],
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
