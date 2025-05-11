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
                config = config_loader.get_config()
                if not config:
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
        if not self.keywords:
            return True

        title = (job.get('titulo') or "").lower()
        description = (job.get('descripcion') or "").lower()
        text = f"{title} {description}"
        return any(kw in text for kw in self.keywords)

    def _matches_location(self, job: Dict[str, Any]) -> bool:
        if not self.target_locations:
            return True

        location = (job.get('ubicacion') or "").lower().strip()
        if not location:
            return False

        if location in self.target_locations:
            return True

        if any(term in location for term in ['remote', 'remoto', 'teletrabajo']) and self.target_remote:
            return True

        return False

    def filter_jobs(self, job_offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not job_offers:
            return []

        filtered = []
        for job in job_offers:
            try:
                if self._matches_keywords(job) and self._matches_location(job):
                    filtered.append(job)
            except Exception:
                logger.error(f"Error al filtrar oferta: {job.get('url', job.get('titulo'))}", exc_info=True)

        return filtered
