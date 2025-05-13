# -*- coding: utf-8 -*-
# /src/super_pipeline.py

"""
Versión super mejorada del pipeline de búsqueda de empleo, integrando todas las mejoras:
- Soporte para scrapers mejorados (LinkedIn, InfoJobs, Computrabajo)
- Cliente HTTP con manejo robusto de errores
- Mejor paralelismo y gestión de recursos
- Estadísticas detalladas
- Estrategias anti-bloqueo avanzadas
"""

import logging
import sys
import os
import traceback
import time
import json
import random
import concurrent.futures
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union

# Configurar logger
logger = logging.getLogger(__name__)

# Asegurar que podamos importar desde el directorio raíz
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    # Importaciones básicas
    from src.utils import config_loader, logging_config
    from src.persistence.database_manager import DatabaseManager
    from src.persistence import file_exporter
    from src.core.job_filter import JobFilter
    from src.core import data_processor
    from src.apis.base_api import BaseAPIClient
    from src.scrapers.base_scraper import BaseScraper

    # Verificar disponibilidad del cliente HTTP mejorado
    try:
        from src.utils.http_client_improved import ImprovedHTTPClient
        HTTP_CLIENT_IMPROVED_AVAILABLE = True
        HTTPClientClass = ImprovedHTTPClient
    except ImportError:
        from src.utils.http_client import HTTPClient
        HTTP_CLIENT_IMPROVED_AVAILABLE = False
        HTTPClientClass = HTTPClient

    # Verificar disponibilidad del manejador de errores mejorado
    try:
        from src.utils.error_handler import register_error, clear_error_registry, get_error_summary, make_search_more_robust
        ERROR_HANDLER_AVAILABLE = True
    except ImportError:
        ERROR_HANDLER_AVAILABLE = False
        # Funciones de fallback si no está disponible el error_handler
        def register_error(*args, **kwargs): pass
        def clear_error_registry(*args, **kwargs): pass
        def get_error_summary(*args, **kwargs): return {}
        def make_search_more_robust(params): return [params]
    
    # Importaciones de APIs
    from src.apis.arbeitnow_client import ArbeitnowClient
    from src.apis.jobicy_client import JobicyClient
    from src.apis.jooble_client import JoobleClient
    from src.apis.remoteok_client import RemoteOkClient
    from src.apis.huggingface_client import HuggingFaceClient

    # Verificar disponibilidad del scraper de LinkedIn mejorado
    try:
        from src.scrapers.linkedin_scraper_improved import LinkedInScraperImproved as LinkedInScraper
        LINKEDIN_SCRAPER_IMPROVED_AVAILABLE = True
    except ImportError:
        from src.scrapers.linkedin_scraper import LinkedInScraper
        LINKEDIN_SCRAPER_IMPROVED_AVAILABLE = False
        
    # Verificar disponibilidad del scraper de InfoJobs mejorado
    try:
        from src.scrapers.infojobs_scraper_improved import InfojobsScraperImproved as InfojobsScraper
        INFOJOBS_SCRAPER_IMPROVED_AVAILABLE = True
    except ImportError:
        from src.scrapers.infojobs_scraper import InfojobsScraper
        INFOJOBS_SCRAPER_IMPROVED_AVAILABLE = False
        
    # Verificar disponibilidad del scraper de Computrabajo mejorado
    try:
        from src.scrapers.computrabajo_scraper_improved import ComputrabajoScraperImproved as ComputrabajoScraper
        COMPUTRABAJO_SCRAPER_IMPROVED_AVAILABLE = True
    except ImportError:
        from src.scrapers.computrabajo_scraper import ComputrabajoScraper
        COMPUTRABAJO_SCRAPER_IMPROVED_AVAILABLE = False
        
    # Verificar disponibilidad del cliente de Adzuna mejorado
    try:
        from src.apis.adzuna_client_improved import AdzunaClientImproved as AdzunaClient
        ADZUNA_CLIENT_IMPROVED_AVAILABLE = True
    except ImportError:
        from src.apis.adzuna_client import AdzunaClient
        ADZUNA_CLIENT_IMPROVED_AVAILABLE = False
    
    # Importaciones de scrapers
    from src.scrapers.bumeran_scraper import BumeranScraper
    from src.scrapers.empleosnet_scraper import EmpleosNetScraper
    from src.scrapers.getonboard_scraper import GetonboardScraper
    from src.scrapers.multitrabajos_scraper import MultitrabajosScraper
    from src.scrapers.opcionempleo_scraper import OpcionempleoScraper
    from src.scrapers.porfinempleo_scraper import PorfinempleoScraper
    from src.scrapers.portalempleoec_scraper import PortalempleoecScraper
    from src.scrapers.remoterocketship_scraper import RemoteRocketshipScraper
    from src.scrapers.soyfreelancer_scraper import SoyFreelancerScraper
    from src.scrapers.tecnoempleo_scraper import TecnoempleoScraper
    from src.scrapers.workana_scraper import WorkanaScraper
    from src.scrapers.wellfound_scraper import WellfoundScraper
except ImportError as e:
    print(f"Error CRÍTICO: No se pudieron importar módulos esenciales: {e}")
    print("Asegúrate de que la estructura del proyecto y los __init__.py estén correctos.")
    print("Verifica también que estás ejecutando desde la carpeta raíz del proyecto.")
    sys.exit(1)

# Mapeo de fuentes a sus clases
SOURCE_MAP = {
    # APIs
    'adzuna': AdzunaClient,
    'arbeitnow': ArbeitnowClient,
    'jobicy': JobicyClient,
    'jooble': JoobleClient,
    'remoteok': RemoteOkClient,
    'huggingface': HuggingFaceClient,
    
    # Scrapers
    'bumeran': BumeranScraper,
    'computrabajo': ComputrabajoScraper,
    'empleosnet': EmpleosNetScraper,
    'getonboard': GetonboardScraper,
    'infojobs': InfojobsScraper,
    'linkedin': LinkedInScraper,
    'multitrabajos': MultitrabajosScraper,
    'opcionempleo': OpcionempleoScraper,
    'porfinempleo': PorfinempleoScraper,
    'portalempleoec': PortalempleoecScraper,
    'remoterocketship': RemoteRocketshipScraper,
    'soyfreelancer': SoyFreelancerScraper,
    'tecnoempleo': TecnoempleoScraper,
    'workana': WorkanaScraper,
    'wellfound': WellfoundScraper,
}

class SuperJobSearchPipeline:
    """Pipeline super mejorado para la búsqueda de empleo"""
    
    def __init__(self, settings=None):
        """
        Inicializa el pipeline con la configuración especificada
        
        Args:
            settings (dict, optional): Configuración personalizada. Si no se proporciona,
                                      se cargará la configuración predeterminada.
        """
        self.start_time = time.time()
        self.settings = settings or config_loader.load_settings()
        
        # Inicializar cliente HTTP
        self.http_client = HTTPClientClass()
        
        # Inicializar gestor de base de datos
        self.db_manager = DatabaseManager()
        
        # Inicializar filtro de trabajos
        self.job_filter = JobFilter(self.settings.get('filters', {}))
        
        # Inicializar estadísticas
        self.stats = {
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'duration_seconds': 0,
            'sources': {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'details': {}
            },
            'jobs': {
                'total_raw': 0,
                'total_processed': 0,
                'filtered': 0
            },
            'improvements': {
                'error_handler': ERROR_HANDLER_AVAILABLE,
                'http_client': HTTP_CLIENT_IMPROVED_AVAILABLE,
                'linkedin_scraper': LINKEDIN_SCRAPER_IMPROVED_AVAILABLE,
                'infojobs_scraper': INFOJOBS_SCRAPER_IMPROVED_AVAILABLE,
                'computrabajo_scraper': COMPUTRABAJO_SCRAPER_IMPROVED_AVAILABLE,
                'adzuna_client': ADZUNA_CLIENT_IMPROVED_AVAILABLE
            },
            'error_summary': {}
        }
        
        # Listas para seguimiento
        self.all_jobs = []
        self.filtered_jobs = []
        self.successful_sources = []
        self.failed_sources = []
        
        # Limpiar registro de errores al inicio
        if ERROR_HANDLER_AVAILABLE:
            clear_error_registry()
        
        logger.info("SuperJobSearchPipeline inicializado con mejoras disponibles: "
                  f"HTTP Client mejorado: {HTTP_CLIENT_IMPROVED_AVAILABLE}, "
                  f"Error Handler: {ERROR_HANDLER_AVAILABLE}, "
                  f"LinkedIn Scraper mejorado: {LINKEDIN_SCRAPER_IMPROVED_AVAILABLE}, "
                  f"InfoJobs Scraper mejorado: {INFOJOBS_SCRAPER_IMPROVED_AVAILABLE}, "
                  f"Computrabajo Scraper mejorado: {COMPUTRABAJO_SCRAPER_IMPROVED_AVAILABLE}, "
                  f"Adzuna Client mejorado: {ADZUNA_CLIENT_IMPROVED_AVAILABLE}")
    
    def _get_source_instances(self) -> Dict[str, Union[BaseScraper, BaseAPIClient]]:
        """
        Crea instancias de todas las fuentes habilitadas
        
        Returns:
            Dict[str, Union[BaseScraper, BaseAPIClient]]: Diccionario con nombre de fuente como clave
                                                        e instancia como valor
        """
        enabled_sources = {}
        available_sources = self.settings.get('sources', {})
        
        for source_name, is_enabled in available_sources.items():
            if not is_enabled:
                logger.info(f"Fuente '{source_name}' está deshabilitada en configuración")
                continue
                
            if source_name not in SOURCE_MAP:
                logger.error(f"Fuente '{source_name}' no encontrada en SOURCE_MAP")
                continue
            
            source_class = SOURCE_MAP[source_name]
            try:
                # Crear instancia de la fuente
                source_instance = source_class(http_client=self.http_client)
                enabled_sources[source_name] = source_instance
                logger.info(f"Instancia creada para fuente: {source_name} "
                          f"(Clase: {source_class.__name__})")
            except Exception as e:
                logger.error(f"Error al crear instancia para fuente {source_name}: {str(e)}")
                if ERROR_HANDLER_AVAILABLE:
                    register_error(source_name, "init", str(e), traceback.format_exc())
        
        self.stats['sources']['total'] = len(enabled_sources)
        return enabled_sources
    
    def _fetch_jobs_from_source(self, source_name: str, source_instance: Union[BaseScraper, BaseAPIClient]) -> List[Dict]:
        """
        Obtiene trabajos de una fuente específica
        
        Args:
            source_name: Nombre de la fuente
            source_instance: Instancia de la fuente (API o Scraper)
            
        Returns:
            List[Dict]: Lista de trabajos obtenidos de la fuente
        """
        logger.info(f"Obteniendo trabajos de fuente: {source_name}")
        jobs = []
        
        try:
            # Obtener parámetros de búsqueda para esta fuente
            search_params = self.settings.get('search_params', {}).copy()
            
            # Si hay un manejador de errores disponible, hacer la búsqueda más robusta
            if ERROR_HANDLER_AVAILABLE:
                param_variations = make_search_more_robust(search_params)
                logger.info(f"Generadas {len(param_variations)} variaciones de parámetros para {source_name}")
            else:
                param_variations = [search_params]
            
            # Intentar cada variación de parámetros
            for params in param_variations:
                try:
                    source_jobs = source_instance.get_jobs(**params)
                    if source_jobs:
                        jobs.extend(source_jobs)
                        logger.info(f"Obtenidos {len(source_jobs)} trabajos de {source_name} con parámetros: {params}")
                except Exception as e:
                    error_msg = f"Error al obtener trabajos de {source_name} con parámetros {params}: {str(e)}"
                    logger.error(error_msg)
                    if ERROR_HANDLER_AVAILABLE:
                        register_error(source_name, "get_jobs", str(e), traceback.format_exc())
            
            # Registrar estadísticas
            if jobs:
                self.successful_sources.append(source_name)
                self.stats['sources']['successful'] += 1
                self.stats['sources']['details'][source_name] = {
                    'status': 'success',
                    'jobs_count': len(jobs)
                }
                logger.info(f"Éxito: Obtenidos {len(jobs)} trabajos de {source_name}")
            else:
                self.failed_sources.append(source_name)
                self.stats['sources']['failed'] += 1
                self.stats['sources']['details'][source_name] = {
                    'status': 'failed',
                    'reason': 'No se obtuvieron trabajos'
                }
                logger.warning(f"No se obtuvieron trabajos de {source_name}")
                
        except Exception as e:
            self.failed_sources.append(source_name)
            self.stats['sources']['failed'] += 1
            self.stats['sources']['details'][source_name] = {
                'status': 'error',
                'reason': str(e)
            }
            logger.error(f"Error al procesar fuente {source_name}: {str(e)}")
            if ERROR_HANDLER_AVAILABLE:
                register_error(source_name, "process", str(e), traceback.format_exc())
        
        return jobs
    
    def run(self) -> Dict[str, Any]:
        """
        Ejecuta el pipeline completo
        
        Returns:
            Dict[str, Any]: Resultados del pipeline incluyendo estadísticas
        """
        logger.info("Iniciando SuperJobSearchPipeline")
        
        # Obtener instancias de fuentes
        sources = self._get_source_instances()
        logger.info(f"Fuentes habilitadas: {list(sources.keys())}")
        
        # Procesar fuentes API y Scrapers en paralelo con estrategias diferentes
        api_sources = {name: instance for name, instance in sources.items() 
                      if isinstance(instance, BaseAPIClient)}
        scraper_sources = {name: instance for name, instance in sources.items() 
                          if isinstance(instance, BaseScraper)}
        
        logger.info(f"Procesando {len(api_sources)} fuentes API en paralelo")
        logger.info(f"Procesando {len(scraper_sources)} scrapers en bloques secuenciales")
        
        # Procesar APIs en paralelo (son más rápidas y resistentes)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(api_sources)) as executor:
            future_to_source = {
                executor.submit(self._fetch_jobs_from_source, name, instance): name 
                for name, instance in api_sources.items()
            }
            
            for future in concurrent.futures.as_completed(future_to_source):
                source_name = future_to_source[future]
                try:
                    jobs = future.result()
                    if jobs:
                        self.all_jobs.extend(jobs)
                except Exception as e:
                    logger.error(f"Error en ejecución paralela para {source_name}: {str(e)}")
        
        # Procesar scrapers en grupos pequeños para evitar problemas de bloqueo
        # Dividimos en grupos más pequeños y añadimos pausas entre ellos
        scraper_names = list(scraper_sources.keys())
        random.shuffle(scraper_names)  # Orden aleatorio para distribuir la carga
        
        # Procesamos los scrapers en bloques de 3 con pausas entre bloques
        batch_size = 3
        for i in range(0, len(scraper_names), batch_size):
            batch = scraper_names[i:i+batch_size]
            logger.info(f"Procesando lote de scrapers: {batch}")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(batch)) as executor:
                future_to_source = {
                    executor.submit(self._fetch_jobs_from_source, name, scraper_sources[name]): name 
                    for name in batch
                }
                
                for future in concurrent.futures.as_completed(future_to_source):
                    source_name = future_to_source[future]
                    try:
                        jobs = future.result()
                        if jobs:
                            self.all_jobs.extend(jobs)
                    except Exception as e:
                        logger.error(f"Error en ejecución por lotes para {source_name}: {str(e)}")
            
            # Pausa entre lotes para evitar detecciones anti-scraping
            if i + batch_size < len(scraper_names):
                pause_time = random.uniform(3, 8)
                logger.info(f"Pausa de {pause_time:.2f} segundos entre lotes de scrapers")
                time.sleep(pause_time)
        
        # Actualizar estadísticas de trabajos
        self.stats['jobs']['total_raw'] = len(self.all_jobs)
        logger.info(f"Total de trabajos sin procesar: {len(self.all_jobs)}")
        
        # Procesar y filtrar trabajos
        if self.all_jobs:
            # Normalizar y enriquecer datos
            processed_jobs = data_processor.process_jobs_batch(self.all_jobs)
            self.stats['jobs']['total_processed'] = len(processed_jobs)
            
            # Filtrar trabajos según criterios
            self.filtered_jobs = self.job_filter.filter_jobs(processed_jobs)
            self.stats['jobs']['filtered'] = len(self.filtered_jobs)
            
            # Guardar en base de datos
            self.db_manager.save_jobs(self.filtered_jobs)
            
            # Exportar a CSV
            csv_path = file_exporter.export_to_csv(self.filtered_jobs)
            logger.info(f"Trabajos exportados a: {csv_path}")
            
            # Guardar todos los trabajos para referencia
            all_jobs_path = file_exporter.export_to_csv(
                processed_jobs, 
                filename=f"ofertas_todas_{datetime.now().strftime('%Y-%m-%d')}.csv"
            )
            logger.info(f"Todos los trabajos exportados a: {all_jobs_path}")
        
        # Completar estadísticas
        self.stats['end_time'] = datetime.now().isoformat()
        self.stats['duration_seconds'] = time.time() - self.start_time
        
        # Añadir resumen de errores si está disponible
        if ERROR_HANDLER_AVAILABLE:
            self.stats['error_summary'] = get_error_summary()
        
        # Guardar estadísticas
        stats_file = Path(project_root) / "data" / "stats" / f"pipeline_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        stats_file.parent.mkdir(exist_ok=True)
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Estadísticas guardadas en: {stats_file}")
        logger.info(f"Pipeline completado en {self.stats['duration_seconds']:.2f} segundos.")
        logger.info(f"Fuentes exitosas: {len(self.successful_sources)}/{self.stats['sources']['total']}")
        logger.info(f"Trabajos encontrados: {self.stats['jobs']['total_raw']} sin procesar, "
                  f"{self.stats['jobs']['filtered']} después de filtrar")
        
        return {
            'raw_jobs': self.stats['jobs']['total_raw'],
            'processed_jobs': self.stats['jobs']['total_processed'],
            'filtered_jobs': self.stats['jobs']['filtered'],
            'successful_sources': len(self.successful_sources),
            'failed_sources': len(self.failed_sources),
            'message': 'Pipeline completado con éxito',
            'duration_seconds': self.stats['duration_seconds']
        }


def run_job_search_pipeline_super() -> Dict[str, Any]:
    """
    Función principal para ejecutar el super pipeline de búsqueda
    
    Returns:
        Dict[str, Any]: Resultados del pipeline
    """
    try:
        # Configurar logging
        logging_config.setup_logging()
        
        # Ejecutar pipeline
        pipeline = SuperJobSearchPipeline()
        result = pipeline.run()
        
        return result
    except Exception as e:
        logger.error(f"Error fatal en SuperJobSearchPipeline: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'raw_jobs': 0,
            'processed_jobs': 0,
            'filtered_jobs': 0,
            'successful_sources': 0,
            'failed_sources': 0,
            'message': f'Error en pipeline: {str(e)}',
            'duration_seconds': 0
        }


if __name__ == "__main__":
    result = run_job_search_pipeline_super()
    print(json.dumps(result, indent=2, ensure_ascii=False))
