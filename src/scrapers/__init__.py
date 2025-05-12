# -*- coding: utf-8 -*-
# /src/scrapers/__init__.py

"""
Módulo de Scrapers para sitios web de empleo.
Contiene todas las implementaciones específicas de scrapers para distintos portales.
"""

from src.scrapers.base_scraper import BaseScraper
from src.scrapers.bumeran_scraper import BumeranScraper
from src.scrapers.computrabajo_scraper import ComputrabajoScraper
from src.scrapers.empleosnet_scraper import EmpleosNetScraper
from src.scrapers.getonboard_scraper import GetonboardScraper
from src.scrapers.infojobs_scraper import InfojobsScraper
from src.scrapers.multitrabajos_scraper import MultitrabajosScraper
from src.scrapers.porfinempleo_scraper import PorfinempleoScraper
from src.scrapers.portalempleoec_scraper import PortalempleoecScraper
from src.scrapers.remoterocketship_scraper import RemoteRocketshipScraper
from src.scrapers.tecnoempleo_scraper import TecnoempleoScraper
from src.scrapers.workana_scraper import WorkanaScraper
from src.scrapers.soyfreelancer_scraper import SoyFreelancerScraper
from src.scrapers.weworkremotely_scraper import WeWorkRemotelyScraper
from src.scrapers.linkedin_scraper import LinkedInScraper
from src.scrapers.wellfound_scraper import WellfoundScraper

# Hacer disponibles los scrapers para importación directa desde el módulo
__all__ = [
    'BaseScraper',
    'BumeranScraper',
    'ComputrabajoScraper',
    'EmpleosNetScraper',
    'GetonboardScraper',
    'InfojobsScraper',
    'MultitrabajosScraper',
    'PorfinempleoScraper',
    'PortalempleoecScraper',
    'RemoteRocketshipScraper',
    'TecnoempleoScraper',
    'WorkanaScraper',
    'SoyFreelancerScraper',
    'WeWorkRemotelyScraper',
    'LinkedInScraper',
    'WellfoundScraper'
]