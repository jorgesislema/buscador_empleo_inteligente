# -*- coding: utf-8 -*-
# /src/main_improved.py

"""
Versión mejorada del punto de entrada principal del Buscador de Empleo Inteligente.

Esta versión incluye:
1. Mejor manejo de errores para fuentes fallidas
2. Estrategia más robusta para búsquedas y filtrado
3. Sistema de reintentos inteligente
4. Estadísticas detalladas de ejecución
5. Paralelización optimizada
"""

import logging
import sys
import traceback
import time
import concurrent.futures
from pathlib import Path

logger = logging.getLogger(__name__)

# Asegurar que podamos importar desde el directorio raíz
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.utils import config_loader, logging_config
    from src.utils.http_client_improved import ImprovedHTTPClient  # Usamos la versión mejorada
    from src.utils.error_handler import register_error, clear_error_registry, get_error_summary
    from src.persistence.database_manager import DatabaseManager
    from src.persistence import file_exporter
    from src.core.job_filter import JobFilter
    from src.core import data_processor
    from src.apis.base_api import BaseAPIClient
    from src.scrapers.base_scraper import BaseScraper    # Importaciones de APIs y scrapers
    from src.apis.adzuna_client import AdzunaClient
    from src.apis.adzuna_client import AdzunaClient
    from src.apis.remoteok_client import RemoteOkClient
    from src.apis.huggingface_client import HuggingFaceClient    # Intentar importar el scraper mejorado de LinkedIn si está disponible
    try:
        from src.scrapers.linkedin_scraper_improved import LinkedInScraperImproved as LinkedInScraper
        LINKEDIN_SCRAPER_IMPROVED_AVAILABLE = True
        print("Se utilizará la versión mejorada del scraper de LinkedIn")
    except ImportError:
        from src.scrapers.linkedin_scraper import LinkedInScraper
        LINKEDIN_SCRAPER_IMPROVED_AVAILABLE = False
        print("Se utilizará la versión estándar del scraper de LinkedIn")

    from src.scrapers.bumeran_scraper import BumeranScraper
    from src.scrapers.computrabajo_scraper import ComputrabajoScraper
    from src.scrapers.empleosnet_scraper import EmpleosNetScraper
    from src.scrapers.getonboard_scraper import GetonboardScraper
    from src.scrapers.infojobs_scraper import InfojobsScraper
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

logger = logging.getLogger(__name__)

# Mapeo de fuentes a sus clases correspondientes
SOURCE_MAP = {
    "adzuna": {"class": AdzunaClient, "type": "apis"},
    "arbeitnow": {"class": ArbeitnowClient, "type": "apis"},
    "jobicy": {"class": JobicyClient, "type": "apis"},
    "jooble": {"class": JoobleClient, "type": "apis"},
    "remoteok": {"class": RemoteOkClient, "type": "apis"},
    "huggingface": {"class": HuggingFaceClient, "type": "apis"},
    "bumeran": {"class": BumeranScraper, "type": "scrapers"},
    "computrabajo": {"class": ComputrabajoScraper, "type": "scrapers"},
    "empleosnet": {"class": EmpleosNetScraper, "type": "scrapers"},
    "getonboard": {"class": GetonboardScraper, "type": "scrapers"},
    "infojobs": {"class": InfojobsScraper, "type": "scrapers"},
    "multitrabajos": {"class": MultitrabajosScraper, "type": "scrapers"},
    "opcionempleo": {"class": OpcionempleoScraper, "type": "scrapers"},
    "porfinempleo": {"class": PorfinempleoScraper, "type": "scrapers"},
    "portalempleoec": {"class": PortalempleoecScraper, "type": "scrapers"},
    "remoterocketship": {"class": RemoteRocketshipScraper, "type": "scrapers"},
    "soyfreelancer": {"class": SoyFreelancerScraper, "type": "scrapers"},
    "tecnoempleo": {"class": TecnoempleoScraper, "type": "scrapers"},
    "workana": {"class": WorkanaScraper, "type": "scrapers"},
    "linkedin": {"class": LinkedInScraper, "type": "scrapers"},
    "wellfound": {"class": WellfoundScraper, "type": "scrapers"},
}

class JobSearchPipeline:
    """
    Clase que encapsula la lógica del pipeline de búsqueda de empleos.
    Esta estructura facilita el manejo de contexto y estadísticas.
    """
class JobSearchPipeline:
    """
    Clase que encapsula la lógica del pipeline de búsqueda de empleos.
    Esta estructura facilita el manejo de contexto y estadísticas.
    """
    def __init__(self):
        self.config = None
        self.http_client = None
        self.db_manager = None
        self.job_filter = None
        self.active_sources = []
        self.successful_sources = []
        self.failed_sources = []
        self.all_raw_jobs = []
        self.processed_jobs = []
        self.filtered_jobs = []
        self.start_time = time.time()
        clear_error_registry()  # Limpiar registro de errores al inicio
        logger.info("**** Iniciando Pipeline Mejorado de Búsqueda de Empleo ****")
        logger.info("*" * 60)
        
        self.config = config_loader.get_config()
        if not self.config:
            logger.critical("¡Fallo al cargar la configuración! Abortando pipeline.")
            return False
        
        logger.info("Inicializando herramientas mejoradas: ImprovedHTTPClient, DatabaseManager, JobFilter...")
        self.http_client = ImprovedHTTPClient()
        self.db_manager = DatabaseManager()
        self.job_filter = JobFilter()
        
        # Registrar qué componentes mejorados están disponibles
        logger.info("Módulos mejorados disponibles:")
        logger.info(f"- Cliente HTTP mejorado: Activo")
        logger.info(f"- Manejador de errores: {'Activo' if 'error_handler' in sys.modules else 'No disponible'}")
        logger.info(f"- LinkedIn Scraper mejorado: {'Activo' if LINKEDIN_SCRAPER_IMPROVED_AVAILABLE else 'No disponible'}")
        
        return True
    
    def load_sources(self):
        """Carga e inicializa las fuentes de datos habilitadas"""
        logger.info("Identificando y cargando fuentes habilitadas desde settings.yaml...")
        sources_config = self.config.get('sources', {})
        if not sources_config:
            logger.warning("No se encontró la sección 'sources' en la configuración. No se ejecutarán fuentes.")
            return False
        
        for source_type in ['apis', 'scrapers']:
            for source_name, source_cfg in sources_config.get(source_type, {}).items():
                if source_cfg and source_cfg.get('enabled', False):
                    logger.info(f"Fuente '{source_name}' ({source_type}) está habilitada.")
                    if source_name in SOURCE_MAP:
                        SourceClass = SOURCE_MAP[source_name]["class"]
                        try:
                            instance = SourceClass(http_client=self.http_client, config=source_cfg)
                            self.active_sources.append(instance)
                            logger.info(f"Instancia de {SourceClass.__name__} creada exitosamente.")
                        except Exception as e:
                            logger.error(f"Error al instanciar {SourceClass.__name__} para '{source_name}'. Se omitirá esta fuente.", exc_info=True)
                            self.failed_sources.append(f"{source_name} (error de inicialización)")
                            register_error('init_errors', source_name, str(e))
                    else:
                        logger.warning(f"Fuente '{source_name}' habilitada en config, ¡pero no se encontró su clase en SOURCE_MAP!")
                        self.failed_sources.append(f"{source_name} (no encontrada en SOURCE_MAP)")
        
        if not self.active_sources:
            logger.warning("¡No hay fuentes activas configuradas para ejecutarse! Terminando pipeline.")
            return False
        
        logger.info(f"Se han activado {len(self.active_sources)} fuentes de datos.")
        return True
    
    def create_search_parameters(self):
        """Crea variaciones de parámetros de búsqueda para obtener más resultados"""
        all_keywords = (self.config.get('job_titles', []) or []) + \
                      (self.config.get('tools_technologies', []) or []) + \
                      (self.config.get('topics', []) or [])
        main_location = (self.config.get('locations', []) or [None])[0]
        
        # Parámetros principales
        search_params_variations = [
            # Parámetros completos
            {
                'keywords': all_keywords,
                'location': main_location
            }
        ]
        
        # Grupos más específicos de keywords
        keyword_groups = [
            # Solo títulos de trabajo
            {'keywords': self.config.get('job_titles', []) or [], 'location': main_location},
            # Solo herramientas/tecnologías
            {'keywords': self.config.get('tools_technologies', []) or [], 'location': main_location},
            # Solo temas generales
            {'keywords': self.config.get('topics', []) or [], 'location': main_location}
        ]
        
        # Añadir grupos no vacíos a las variaciones
        for group in keyword_groups:
            if group['keywords']:
                search_params_variations.append(group)
        
        # Si hay demasiadas keywords, crear versiones con menos keywords
        if len(all_keywords) > 20:
            # Versión con solo las 10 primeras keywords
            search_params_variations.append({
                'keywords': all_keywords[:10],
                'location': main_location
            })
            # Versión con keywords 11-20
            search_params_variations.append({
                'keywords': all_keywords[10:20],
                'location': main_location
            })
        
        # Palabras clave técnicas populares para búsqueda más específica
        tech_keywords = [k for k in all_keywords if k.lower() in 
                       ['python', 'javascript', 'react', 'data', 'developer', 'programador', 
                        'software', 'web', 'frontend', 'backend', 'data scientist']]
        if tech_keywords:
            search_params_variations.append({
                'keywords': tech_keywords[:10],
                'location': main_location
            })
        
        # Versión sin ubicación para fuentes globales
        search_params_variations.append({
            'keywords': all_keywords[:10] if len(all_keywords) > 10 else all_keywords,
            'location': None
        })
        
        global_search_params = search_params_variations[0]
        logger.info(f"Parámetros principales: {len(all_keywords)} keywords, location hint: '{main_location}'")
        logger.info(f"Se usarán {len(search_params_variations)} variaciones de parámetros para maximizar resultados")
        
        return global_search_params, search_params_variations
    
    def process_source(self, source_instance, global_params, all_variations):
        """
        Procesa una fuente individual de manera robusta.
        Esta función está diseñada para ser ejecutada en paralelo o secuencialmente.
        """
        source_name = source_instance.source_name
        logger.info(f"Ejecutando fetch_jobs para: {source_name}...")
        
        jobs_from_source = []
        try:
            # Intentar con el conjunto principal de parámetros primero
            jobs_from_source = source_instance.fetch_jobs(global_params)
            
            # Si no se encontraron ofertas o se encontraron pocas, intentar con otras variaciones
            if not jobs_from_source or len(jobs_from_source) < 5:
                logger.info(f"Pocas o ninguna oferta para '{source_name}' con parámetros principales. Intentando variaciones...")
                
                for i, params in enumerate(all_variations[1:], 1):
                    try:
                        logger.info(f"Intentando variación {i} para '{source_name}'")
                        variation_jobs = source_instance.fetch_jobs(params)
                        if variation_jobs:
                            logger.info(f"¡Éxito! Variación {i} encontró {len(variation_jobs)} ofertas para '{source_name}'")
                            # Solo añadir ofertas que no estén ya en la lista (evitar duplicados)
                            new_job_urls = {job.get('url') for job in jobs_from_source if job.get('url')}
                            for job in variation_jobs:
                                if job.get('url') and job.get('url') not in new_job_urls:
                                    jobs_from_source.append(job)
                                    new_job_urls.add(job.get('url'))
                            
                            # Si ya tenemos suficientes ofertas, detenemos la búsqueda
                            if len(jobs_from_source) > 30:
                                logger.info(f"Ya tenemos {len(jobs_from_source)} ofertas para '{source_name}'. Deteniendo búsqueda.")
                                break
                    except Exception as e:
                        logger.error(f"Error en variación {i} para '{source_name}': {str(e)}")
                        register_error('variation_error', source_name, f"Variación {i}: {str(e)}")
            
            if jobs_from_source:
                # Asegurar que cada oferta tenga el campo 'fuente' correctamente asignado
                for job in jobs_from_source:
                    if 'fuente' not in job or not job['fuente']:
                        job['fuente'] = source_name
                
                logger.info(f"Fuente '{source_name}' devolvió {len(jobs_from_source)} ofertas.")
                return source_name, jobs_from_source, True  # (nombre, ofertas, éxito)
            else:
                logger.info(f"Fuente '{source_name}' no devolvió ofertas después de intentar todas las variaciones.")
                return source_name, [], False  # (nombre, ofertas vacías, fallo)
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"¡Error al ejecutar fetch_jobs para '{source_name}'! Error: {error_msg}", exc_info=True)
            register_error('fetch_error', source_name, error_msg)
            return source_name, [], False  # (nombre, ofertas vacías, fallo)
    
    def collect_data(self):
        """
        Recolecta datos de todas las fuentes, utilizando paralelismo cuando está configurado.
        """
        if not self.active_sources:
            return False
        
        logger.info(f"--- Iniciando Recolección de Datos ({len(self.active_sources)} fuentes activas) ---")
        
        global_params, all_variations = self.create_search_parameters()
        scraping_config = self.config.get('scraping', {})
        use_parallel = scraping_config.get('parallel_sources', True)
        max_workers = min(scraping_config.get('parallel_workers', 4), len(self.active_sources))
        
        if use_parallel and max_workers > 1:
            logger.info(f"Procesando fuentes en paralelo con {max_workers} trabajadores")
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Crear las tareas
                future_to_source = {
                    executor.submit(self.process_source, source, global_params, all_variations): source.source_name
                    for source in self.active_sources
                }
                
                # Procesar los resultados a medida que finalizan
                for future in concurrent.futures.as_completed(future_to_source):
                    source_name = future_to_source[future]
                    try:
                        name, jobs, success = future.result()
                        if success and jobs:
                            self.all_raw_jobs.extend(jobs)
                            self.successful_sources.append(name)
                        else:
                            self.failed_sources.append(f"{name} (sin resultados)")
                    except Exception as e:
                        logger.error(f"Error procesando resultados de {source_name}: {str(e)}", exc_info=True)
                        self.failed_sources.append(f"{source_name} (error al procesar resultados)")
        else:
            logger.info("Procesando fuentes secuencialmente")
            for source in self.active_sources:
                name, jobs, success = self.process_source(source, global_params, all_variations)
                if success and jobs:
                    self.all_raw_jobs.extend(jobs)
                    self.successful_sources.append(name)
                else:
                    self.failed_sources.append(f"{name} (sin resultados)")
        
        # Resumen de fuentes exitosas y fallidas
        logger.info(f"--- Recolección Finalizada. Total ofertas 'crudas' obtenidas: {len(self.all_raw_jobs)} ---")
        logger.info(f"Fuentes exitosas ({len(self.successful_sources)}): {', '.join(self.successful_sources)}")
        logger.info(f"Fuentes sin resultados o con errores ({len(self.failed_sources)}): {', '.join(self.failed_sources)}")
        
        return len(self.all_raw_jobs) > 0
    
    def process_and_filter_data(self):
        """Procesa y filtra los datos recolectados"""
        if not self.all_raw_jobs:
            logger.warning("No hay ofertas crudas para procesar y filtrar.")
            return False
        
        logger.info("--- Iniciando Procesamiento/Limpieza de Datos ---")
        self.processed_jobs = data_processor.process_job_offers(self.all_raw_jobs)
        logger.info(f"--- Procesamiento Finalizado. {len(self.processed_jobs)} ofertas después de limpieza ---")
        
        logger.info("--- Iniciando Filtrado de Ofertas ---")
        self.filtered_jobs = self.job_filter.filter_jobs(self.processed_jobs)
        logger.info(f"--- Filtrado Finalizado. {len(self.filtered_jobs)} ofertas cumplen los criterios ---")
        
        return True
    
    def save_results(self):
        """Guarda los resultados en la base de datos y exporta a CSV si está configurado"""
        if self.filtered_jobs:
            logger.info("--- Iniciando Inserción en Base de Datos ---")
            try:
                self.db_manager.insert_job_offers(self.filtered_jobs)
                logger.info("--- Inserción en Base de Datos Finalizada ---")
            except Exception as e:
                logger.error(f"Error al insertar en base de datos: {str(e)}", exc_info=True)
                register_error('database_error', 'db_manager', str(e))
        else:
            logger.info("No hay ofertas filtradas para insertar en la base de datos.")
        
        csv_export_enabled = self.config.get('data_storage', {}).get('csv', {}).get('export_enabled', False)
        if csv_export_enabled:
            logger.info("--- Iniciando Exportación a CSV ---")
            try:
                if self.filtered_jobs:
                    # Exportar ambos archivos: todas las ofertas sin filtrar y solo las filtradas
                    file_exporter.export_to_csv(self.filtered_jobs, is_filtered=True, unfiltered_offers=self.processed_jobs)
                    logger.info("--- Exportación a CSV Finalizada (ofertas filtradas y sin filtrar) ---")
                else:
                    # Si no hay ofertas filtradas, exportar solo las sin filtrar
                    logger.info("No hay ofertas filtradas para exportar, pero se exportarán todas las ofertas sin filtrar")
                    file_exporter.export_to_csv([], is_filtered=True, unfiltered_offers=self.processed_jobs)
                    logger.info("--- Exportación a CSV Finalizada (solo ofertas sin filtrar) ---")
            except Exception as e:
                logger.error(f"Error al exportar a CSV: {str(e)}", exc_info=True)
                register_error('export_error', 'file_exporter', str(e))
        else:
            logger.info("Exportación a CSV deshabilitada en la configuración.")
        
        return True
    
    def cleanup(self):
        """Limpieza y resumen final del proceso"""
        logger.info("Cerrando recursos y generando resumen...")
        
        # Cerrar cliente HTTP
        if self.http_client:
            self.http_client.close()
        
        # Calcular tiempo total de ejecución
        execution_time = time.time() - self.start_time
        
        # Generar resumen del proceso
        summary = {
            "execution_time_seconds": execution_time,
            "execution_time_formatted": f"{execution_time/60:.2f} minutos",
            "total_sources_enabled": len(self.active_sources),
            "successful_sources": len(self.successful_sources),
            "failed_sources": len(self.failed_sources),
            "raw_jobs_collected": len(self.all_raw_jobs),
            "processed_jobs": len(self.processed_jobs),
            "filtered_jobs": len(self.filtered_jobs),
            "error_summary": get_error_summary()
        }
        
        # Mostrar resumen
        logger.info("*" * 60)
        logger.info("**** Resumen del Pipeline de Búsqueda de Empleo ****")
        logger.info("*" * 60)
        logger.info(f"Tiempo total de ejecución: {summary['execution_time_formatted']}")
        logger.info(f"Fuentes: {summary['successful_sources']} exitosas, {summary['failed_sources']} fallidas")
        logger.info(f"Ofertas: {summary['raw_jobs_collected']} recolectadas, {summary['processed_jobs']} procesadas, {summary['filtered_jobs']} filtradas")
        
        error_summary = summary["error_summary"]
        if any(count > 0 for count in error_summary.values()):
            logger.warning("Resumen de errores:")
            for error_type, count in error_summary.items():
                if count > 0:
                    logger.warning(f"  - {error_type}: {count}")
        
        # El factor de éxito se calcula como el porcentaje de fuentes exitosas
        if self.active_sources:
            success_factor = (len(self.successful_sources) / len(self.active_sources)) * 100
            logger.info(f"Factor de éxito: {success_factor:.1f}% de las fuentes fueron exitosas")
        
        logger.info("*" * 60)
        logger.info("**** Pipeline de Búsqueda de Empleo Finalizado ****")
        logger.info("*" * 60)
        
        return summary
    
    def run(self):
        """Ejecuta el pipeline completo de búsqueda de empleo"""
        try:
            if not self.initialize():
                return {"status": "error", "message": "Falló la inicialización"}
            
            if not self.load_sources():
                return {"status": "error", "message": "No se pudieron cargar las fuentes"}
            
            if not self.collect_data():
                logger.warning("No se recolectaron ofertas de ninguna fuente.")
                return {"status": "warning", "message": "No se encontraron ofertas"}
            
            self.process_and_filter_data()
            self.save_results()
            summary = self.cleanup()
            
            return {
                "status": "success", 
                "message": "Pipeline ejecutado exitosamente",
                "summary": summary
            }
        
        except Exception as e:
            logger.critical("¡Error fatal durante la ejecución del pipeline!", exc_info=True)
            self.cleanup()  # Intentar limpiar recursos incluso en caso de error
            return {
                "status": "error",
                "message": f"Error fatal: {str(e)}",
                "traceback": traceback.format_exc()
            }


def run_job_search_pipeline():
    """Función envoltorio para mantener compatibilidad con el código existente"""
    pipeline = JobSearchPipeline()
    return pipeline.run()


if __name__ == "__main__":
    print("Ejecutando el pipeline principal mejorado...")
    try:
        result = run_job_search_pipeline()
        
        if result["status"] == "success":
            print("\nPipeline ejecutado exitosamente.")
            summary = result.get("summary", {})
            print(f"Se encontraron {summary.get('filtered_jobs', 0)} ofertas filtradas de {summary.get('raw_jobs_collected', 0)} ofertas recolectadas.")
        else:
            print(f"\n¡{result['status'].upper()}! {result['message']}")
            print("Revisa los logs ('logs/app.log') para más detalles.")
    
    except Exception as e:
        logging.getLogger().critical("¡Ocurrió un error fatal en la ejecución principal!", exc_info=True)
        print(f"\n¡ERROR! El pipeline falló. Revisa los logs ('logs/app.log'). Error: {e}")
