# -*- coding: utf-8 -*-
# /src/core/job_filter.py

"""
Módulo de Filtrado de Ofertas de Empleo.

Aquí reside la lógica para decidir qué ofertas de las recolectadas
nos interesan realmente, basándonos en los criterios definidos en
settings.yaml (keywords y ubicaciones).
"""

import logging
from typing import List, Dict, Any, Set

try:
    from src.utils import config_loader
except ImportError:
    logging.basicConfig(level=logging.WARNING)
    logging.warning("No se pudo importar config_loader en job_filter. Usando criterios vacíos.")
    config_loader = None

logger = logging.getLogger(__name__)

class JobFilter:
    def __init__(self):
        logger.info("Inicializando JobFilter...")
        self.keywords: Set[str] = set()
        self.target_locations: Set[str] = set()
        self.target_remote: bool = False

        try:
            if config_loader:
                config = config_loader.get_config() or {}
                if not isinstance(config, dict):
                    logger.error("No se pudo cargar la configuración para JobFilter. El filtro usará criterios vacíos.")
                    return

                titles = config.get('job_titles', [])
                tools = config.get('tools_technologies', [])
                topics = config.get('topics', [])
                all_keywords = titles + tools + topics

                self.keywords = {kw.lower() for kw in all_keywords if isinstance(kw, str)}
                self.target_locations = {loc.lower() for loc in config.get('locations', []) if isinstance(loc, str)}
                self.target_remote = any('remote' in loc or 'remoto' in loc for loc in self.target_locations)
            else:
                logger.error("config_loader no está disponible. JobFilter usará criterios vacíos.")
        except Exception as e:
            logger.exception("Error durante la inicialización de JobFilter. Usando criterios vacíos.")
            self.keywords = set()
            self.target_locations = set()
            self.target_remote = False

    def _matches_keywords(self, job: Dict[str, Any]) -> bool:
        """
        Verifica si una oferta contiene al menos UNA de las palabras clave de interés.
        Si no hay keywords configuradas, todas las ofertas pasan este filtro.
        """
        if not self.keywords:
            return True

        # Obtener campos relevantes donde buscar keywords
        title = str(job.get('titulo', "")).lower()
        description = str(job.get('descripcion', "")).lower()
        company = str(job.get('empresa', "")).lower()
        text = f"{title} {description} {company}"
        
        # Primero verificamos si aparece alguna palabra clave en el título (prioridad alta)
        for kw in self.keywords:
            if kw in title:
                logger.debug(f"Keyword '{kw}' encontrada en el TÍTULO de la oferta: {job.get('titulo')}")
                return True
                
        # Si el título no contiene palabras clave, verificamos en la descripción completa
        # Consideramos coincidencia si al menos una palabra clave está presente
        for kw in self.keywords:
            if kw in text:
                logger.debug(f"Keyword '{kw}' encontrada en oferta: {job.get('titulo')}")
                return True
        
        # Si la oferta incluye términos relacionados con programación/tecnología, 
        # aunque no coincida exactamente con nuestras keywords, la consideramos
        tech_indicators = ['programador', 'developer', 'ingeniero', 'engineer', 'código', 'code', 
                          'software', 'desarrollo', 'development', 'tech', 'tecnología', 'technology',
                          'computer', 'computación', 'informática', 'it ', ' it,', 'database', 'datos',
                          'data', 'web', 'app', 'aplicación', 'application']
        
        for indicator in tech_indicators:
            if indicator in text:
                logger.debug(f"Indicador tecnológico '{indicator}' encontrado en oferta: {job.get('titulo')}")
                return True
                
        return False

    def _matches_location(self, job: Dict[str, Any]) -> bool:
        """
        Verifica si una oferta coincide con las ubicaciones de interés.
        Si no hay ubicaciones configuradas, todas las ofertas pasan este filtro.
        Las ofertas remotas se aceptan si se ha configurado 'remote'/'remoto' en las ubicaciones.
        """
        # Si no hay restricciones de ubicación, aceptar todas
        if not self.target_locations:
            return True

        location = str(job.get('ubicacion', "")).lower().strip()
        
        # Si no hay información de ubicación pero aceptamos remoto, asumimos que podría ser remoto
        if not location and self.target_remote:
            logger.debug(f"Oferta sin ubicación aceptada como posible remoto: {job.get('titulo')}")
            return True

        # Verificar si la ubicación está explícitamente en nuestra lista
        for target_loc in self.target_locations:
            if target_loc in location:
                logger.debug(f"Ubicación '{target_loc}' coincide con '{location}' en oferta: {job.get('titulo')}")
                return True

        # Verificar si buscamos remotas y esta es remota
        if self.target_remote and any(term in location for term in ['remote', 'remoto', 'teletrabajo', 'trabajo a distancia', 'home office', 'trabajo desde casa']):
            logger.debug(f"Oferta remota identificada: {job.get('titulo')} - {location}")
            return True

        logger.debug(f"Ubicación no coincide: '{location}' para oferta: {job.get('titulo')}")
        return False

    def filter_jobs(self, job_offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Aplica los filtros de keywords y ubicación a las ofertas recibidas.
        Devuelve las ofertas que pasan ambos filtros.
        """
        if not job_offers:
            logger.warning("No hay ofertas para filtrar")
            return []

        filtered = []
        rejected_count = 0
        
        logger.info(f"Filtrando {len(job_offers)} ofertas con {len(self.keywords)} keywords y {len(self.target_locations)} ubicaciones")
        for job in job_offers:
            try:
                matches_keywords = self._matches_keywords(job)
                matches_location = self._matches_location(job)
                
                if matches_keywords and matches_location:
                    logger.debug(f"Oferta aceptada: {job.get('titulo')}")
                    filtered.append(job)
                else:
                    rejected_count += 1
                    if not matches_keywords:
                        logger.debug(f"Oferta rechazada por keywords: {job.get('titulo')}")
                    if not matches_location:
                        logger.debug(f"Oferta rechazada por ubicación: {job.get('titulo')}")
            except Exception as e:
                logger.error(f"Error al filtrar oferta: {job.get('url', job.get('titulo', 'Desconocido'))}", exc_info=True)
        
        logger.info(f"Filtrado completado: {len(filtered)} ofertas aceptadas, {rejected_count} rechazadas")
        
        # Si el resultado del filtrado es muy restrictivo (menos del 10% de ofertas), agregar un warning
        if filtered and len(filtered) < 0.1 * len(job_offers):
            logger.warning("El filtrado es muy restrictivo, considera relajar los criterios")
            
        # Si todas las ofertas fueron rechazadas, aplicar un filtrado menos restrictivo
        if not filtered and job_offers:
            logger.warning("Todas las ofertas fueron rechazadas. Aplicando filtrado más permisivo...")
            # Devolver todas las ofertas si había pocas (menos de 10)
            if len(job_offers) <= 10:
                logger.info(f"Devolviendo todas las {len(job_offers)} ofertas sin filtrar por ser pocas")
                return job_offers
            
            # O devolver hasta 20 ofertas si había muchas
            else:
                sample_size = min(20, len(job_offers))
                logger.info(f"Devolviendo {sample_size} ofertas de muestra de las {len(job_offers)} encontradas")
                return job_offers[:sample_size]
            
        return filtered
