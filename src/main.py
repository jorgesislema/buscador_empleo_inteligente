# -*- coding: utf-8 -*-
# /src/main.py

"""
Punto de Entrada Principal y Orquestador del Buscador de Empleo Inteligente.

Este módulo contiene la función principal 'run_job_search_pipeline' que
ejecuta todo el proceso:
1. Carga configuración y logging.
2. Inicializa herramientas (HTTPClient, DBManager, Filter).
3. Identifica y carga las fuentes de datos (APIs, Scrapers) habilitadas.
4. Ejecuta la recolección de datos de cada fuente.
5. Procesa (limpia) los datos recolectados.
6. Filtra los datos según los criterios definidos.
7. Guarda los datos filtrados en la base de datos.
8. (Opcional) Exporta los datos filtrados a CSV.
"""

import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.utils import config_loader, logging_config
    from src.utils.http_client import HTTPClient
    from src.persistence.database_manager import DatabaseManager
    from src.persistence import file_exporter
    from src.core.job_filter import JobFilter
    from src.core import data_processor
    from src.apis.base_api import BaseAPIClient
    from src.scrapers.base_scraper import BaseScraper

    from src.apis.adzuna_client import AdzunaClient
    from src.apis.arbeitnow_client import ArbeitnowClient
    from src.apis.jobicy_client import JobicyClient
    from src.apis.jooble_client import JoobleClient
    from src.apis.remoteok_client import RemoteOkClient
    from src.apis.huggingface_client import HuggingFaceClient

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
    from src.scrapers.linkedin_scraper import LinkedInScraper
    from src.scrapers.wellfound_scraper import WellfoundScraper
except ImportError as e:
    print(f"Error CRÍTICO: No se pudieron importar módulos esenciales: {e}")
    print("Asegúrate de que la estructura del proyecto y los __init__.py estén correctos.")
    print("Verifica también que estás ejecutando desde la carpeta raíz del proyecto.")
    sys.exit(1)

logger = logging.getLogger(__name__)

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

def run_job_search_pipeline():
    try:
        logging_config.setup_logging()
        logger.info("**********************************************")
        logger.info("**** Iniciando Pipeline Buscador de Empleo ****")
        logger.info("**********************************************")
        config = config_loader.get_config()
        if not config:
            logger.critical("¡Fallo al cargar la configuración! Abortando pipeline.")
            return
    except Exception as e:
        logging.critical(f"Error MUY GRAVE en la configuración inicial: {e}", exc_info=True)
        return

    logger.info("Inicializando herramientas: HTTPClient, DatabaseManager, JobFilter...")
    http_client = HTTPClient()
    db_manager = DatabaseManager()
    job_filter = JobFilter()

    active_sources = []

    logger.info("Identificando y cargando fuentes habilitadas desde settings.yaml...")
    sources_config = config.get('sources', {})
    if not sources_config:
        logger.warning("No se encontró la sección 'sources' en la configuración. No se ejecutarán fuentes.")
        http_client.close()
        return

    # Lista para llevar un registro de cuáles fuentes tuvieron éxito y cuáles fallaron
    successful_sources = []
    failed_sources = []

    for source_type in ['apis', 'scrapers']:
        for source_name, source_cfg in sources_config.get(source_type, {}).items():
            if source_cfg and source_cfg.get('enabled', False):
                logger.info(f"Fuente '{source_name}' ({source_type}) está habilitada.")
                if source_name in SOURCE_MAP:
                    SourceClass = SOURCE_MAP[source_name]["class"]
                    try:
                        instance = SourceClass(http_client=http_client, config=source_cfg)
                        active_sources.append(instance)
                        logger.info(f"Instancia de {SourceClass.__name__} creada exitosamente.")
                    except Exception as e:
                        logger.error(f"Error al instanciar {SourceClass.__name__} para '{source_name}'. Se omitirá esta fuente.", exc_info=True)
                        failed_sources.append(f"{source_name} (error de inicialización)")
                else:
                    logger.warning(f"Fuente '{source_name}' habilitada en config, ¡pero no se encontró su clase en SOURCE_MAP!")
                    failed_sources.append(f"{source_name} (no encontrada en SOURCE_MAP)")

    if not active_sources:
        logger.warning("¡No hay fuentes activas configuradas para ejecutarse! Terminando pipeline.")
        http_client.close()
        return

    all_keywords = (config.get('job_titles', []) or []) + \
                   (config.get('tools_technologies', []) or []) + \
                   (config.get('topics', []) or [])
    main_location = (config.get('locations', []) or [None])[0]

    # Construir varios conjuntos de parámetros de búsqueda para aumentar la cobertura
    search_params_variations = [
        # Parámetros completos
        {
            'keywords': all_keywords,
            'location': main_location
        },
        # Solo palabras clave técnicas/herramientas
        {
            'keywords': config.get('tools_technologies', []) or [],
            'location': main_location
        },
        # Solo títulos de trabajo
        {
            'keywords': config.get('job_titles', []) or [],
            'location': main_location
        }
    ]
    
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
    
    global_search_params = search_params_variations[0]  # Usar la primera variación como principal
    logger.info(f"Parámetros de búsqueda globales: {len(all_keywords)} keywords, location hint: '{main_location}'")
    logger.info(f"Se usarán {len(search_params_variations)} variaciones de parámetros para aumentar resultados")

    logger.info(f"--- Iniciando Recolección de Datos ({len(active_sources)} fuentes activas) ---")
    all_raw_jobs = []
    for source_instance in active_sources:
        source_name = source_instance.source_name
        logger.info(f"Ejecutando fetch_jobs para: {source_name}...")
        
        jobs_from_source = []
        try:
            # Intentar con el conjunto principal de parámetros primero
            jobs_from_source = source_instance.fetch_jobs(global_search_params)
            
            # Si no se encontraron ofertas, intentar con otras variaciones
            if not jobs_from_source:
                logger.info(f"No se encontraron ofertas para '{source_name}' con parámetros principales. Intentando con variaciones...")
                for i, params in enumerate(search_params_variations[1:], 1):
                    logger.info(f"Intentando variación {i} para '{source_name}'")
                    variation_jobs = source_instance.fetch_jobs(params)
                    if variation_jobs:
                        logger.info(f"¡Éxito! Variación {i} encontró {len(variation_jobs)} ofertas para '{source_name}'")
                        jobs_from_source.extend(variation_jobs)
                        break
            
            if jobs_from_source:
                # Asegurar que cada oferta tenga el campo 'fuente' correctamente asignado
                for job in jobs_from_source:
                    if 'fuente' not in job or not job['fuente']:
                        job['fuente'] = source_name
                        
                logger.info(f"Fuente '{source_name}' devolvió {len(jobs_from_source)} ofertas.")
                all_raw_jobs.extend(jobs_from_source)
                successful_sources.append(source_name)
            else:
                logger.info(f"Fuente '{source_name}' no devolvió ofertas después de intentar todas las variaciones.")
                failed_sources.append(f"{source_name} (sin resultados)")
        except Exception as e:
            logger.error(f"¡Error al ejecutar fetch_jobs para '{source_name}'! Se continuará con la siguiente fuente.", exc_info=True)
            failed_sources.append(f"{source_name} (error: {str(e)[:100]}...)")

    # Resumen de fuentes exitosas y fallidas
    logger.info(f"--- Recolección Finalizada. Total ofertas 'crudas' obtenidas: {len(all_raw_jobs)} ---")
    logger.info(f"Fuentes exitosas ({len(successful_sources)}): {', '.join(successful_sources)}")
    logger.info(f"Fuentes sin resultados o con errores ({len(failed_sources)}): {', '.join(failed_sources)}")

    logger.info("--- Iniciando Procesamiento/Limpieza de Datos ---")
    processed_jobs = data_processor.process_job_offers(all_raw_jobs)
    logger.info(f"--- Procesamiento Finalizado. {len(processed_jobs)} ofertas después de limpieza ---")

    logger.info("--- Iniciando Filtrado de Ofertas ---")
    filtered_jobs = job_filter.filter_jobs(processed_jobs)
    logger.info(f"--- Filtrado Finalizado. {len(filtered_jobs)} ofertas cumplen los criterios ---")

    if filtered_jobs:
        logger.info("--- Iniciando Inserción en Base de Datos ---")
        db_manager.insert_job_offers(filtered_jobs)
        logger.info("--- Inserción en Base de Datos Finalizada ---")
    else:
        logger.info("No hay ofertas filtradas para insertar en la base de datos.")

    csv_export_enabled = config.get('data_storage', {}).get('csv', {}).get('export_enabled', False)
    if csv_export_enabled:
        logger.info("--- Iniciando Exportación a CSV ---")
        if filtered_jobs:
            # Exportar ambos archivos: todas las ofertas sin filtrar y solo las filtradas
            file_exporter.export_to_csv(filtered_jobs, is_filtered=True, unfiltered_offers=processed_jobs)
            logger.info("--- Exportación a CSV Finalizada (ofertas filtradas y sin filtrar) ---")
        else:
            # Si no hay ofertas filtradas, exportar solo las sin filtrar
            logger.info("No hay ofertas filtradas para exportar, pero se exportarán todas las ofertas sin filtrar")
            file_exporter.export_to_csv([], is_filtered=True, unfiltered_offers=processed_jobs)
            logger.info("--- Exportación a CSV Finalizada (solo ofertas sin filtrar) ---")
    else:
        logger.info("Exportación a CSV deshabilitada en la configuración.")

    logger.info("Cerrando cliente HTTP...")
    http_client.close()

    logger.info("********************************************")
    logger.info("**** Pipeline Buscador de Empleo Finalizado ****")
    logger.info("********************************************")

if __name__ == "__main__":
    print("Ejecutando el pipeline principal manualmente...")
    try:
        run_job_search_pipeline()
        print("\nPipeline ejecutado exitosamente.")
    except Exception as e:
        logging.getLogger().critical("¡Ocurrió un error fatal en la ejecución principal!", exc_info=True)
        print(f"\n¡ERROR! El pipeline falló. Revisa los logs ('logs/app.log'). Error: {e}")
