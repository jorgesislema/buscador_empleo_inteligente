# -*- coding: utf-8 -*-
# /scripts/run_scraper_manualmente.py

"""
Script para Ejecutar un Scraper o Cliente API Específico Manualmente.

Muy útil para probar y depurar una fuente de datos individual sin
ejecutar todo el flujo principal de la aplicación.

Uso:
    python scripts/run_scraper_manualmente.py <nombre_fuente>

Donde <nombre_fuente> es la clave usada en settings.yaml (ej: 'computrabajo', 'adzuna').
"""

import argparse # Para leer argumentos de la línea de comandos.
import logging
import pprint   # Para imprimir diccionarios de forma legible.
import sys
from pathlib import Path

# Añadimos la carpeta raíz del proyecto al PYTHONPATH para asegurar importaciones
# Asumimos que este script está en /scripts/ y la raíz es un nivel arriba.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Importamos nuestras utilidades y clases base/específicas
# ¡Tenemos que importar TODAS las clases de scraper/api que podríamos querer ejecutar!
try:
    from src.utils import config_loader, logging_config
    from src.utils.http_client import HTTPClient

    # --- APIs ---
    from src.apis.adzuna_client import AdzunaClient
    from src.apis.arbeitnow_client import ArbeitnowClient
    from src.apis.jobicy_client import JobicyClient
    from src.apis.jooble_client import JoobleClient     # El cliente API, no el scraper
    from src.apis.remoteok_client import RemoteOkClient   # El cliente API, no el scraper

    # --- Scrapers ---
    from src.scrapers.bumeran_scraper import BumeranScraper
    from src.scrapers.computrabajo_scraper import ComputrabajoScraper
    from src.scrapers.empleosnet_scraper import EmpleosNetScraper
    from src.scrapers.getonboard_scraper import GetonboardScraper
    from src.scrapers.infojobs_scraper import InfojobsScraper
    from src.scrapers.multitrabajos_scraper import MultitrabajosScraper
    from src.scrapers.opcionempleo_scraper import OpcionempleoScraper
    from src.scrapers.porfinempleo_scraper import PorfinempleoScraper
    from src.scrapers.portalempleoec_scraper import PortalempleoecScraper # El que apunta a Encuentra Empleo
    from src.scrapers.remoterocketship_scraper import RemoteRocketshipScraper
    from src.scrapers.soyfreelancer_scraper import SoyFreelancerScraper
    from src.scrapers.tecnoempleo_scraper import TecnoempleoScraper
    from src.scrapers.workana_scraper import WorkanaScraper
    # Añadir aquí imports de futuros scrapers/apis...
    # from src.scrapers.nuevoscraper_scraper import NuevoScraper

except ImportError as e:
    print(f"Error: No se pudieron importar módulos necesarios: {e}")
    print("Asegúrate de ejecutar este script desde la carpeta raíz del proyecto (la que contiene 'src', 'scripts', etc.)")
    print(f"PYTHONPATH actual: {sys.path}")
    sys.exit(1)

# Obtenemos un logger para este script.
logger = logging.getLogger("manual_run")

# Mapeo de nombres (los que usamos en settings.yaml) a las clases correspondientes.
# ¡Fundamental para saber qué objeto crear!
# Separamos APIs y Scrapers para claridad y para obtener su config del lugar correcto.
SOURCE_MAP = {
    # APIs
    "adzuna": {"class": AdzunaClient, "type": "apis"},
    "arbeitnow": {"class": ArbeitnowClient, "type": "apis"},
    "jobicy": {"class": JobicyClient, "type": "apis"},
    "jooble": {"class": JoobleClient, "type": "apis"}, # Apuntamos al API Client
    "remoteok": {"class": RemoteOkClient, "type": "apis"}, # Apuntamos al API Client
    # Scrapers
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
    # Añadir aquí nuevas fuentes a medida que se creen los archivos .py
    # "nuevoscraper": {"class": NuevoScraper, "type": "scrapers"},
}

def main():
    """Función principal que ejecuta la extracción de ofertas de empleo."""
    # Cargamos la configuración
    config_data = config_loader.load_settings()
    if not config_data:
        logger.error("No se pudo cargar la configuración. Abortando.")
        return 1

    # Creamos un cliente HTTP para compartir entre todos los scrapers/APIs
    http_client = HTTPClient()

    # Lista para almacenar las ofertas de empleo
    all_job_offers = []

    # Tipos de fuentes a ejecutar (None = todas, o lista de tipos: ['apis', 'scrapers'])
    source_types_to_run = None  # Cambiar a ['apis'] o ['scrapers'] para ejecutar solo APIs o scrapers

    # Nombres de fuentes específicas a ejecutar (None = todas, o lista de nombres)
    # Por ejemplo: sources_to_run = ['computrabajo', 'infojobs', 'tecnoempleo'] 
    sources_to_run = None  # Ejecutamos TODAS las fuentes habilitadas en settings.yaml

    # Opciones de búsqueda - ¡Podemos expandir con más opciones desde settings.yaml!
    search_options = {
        # Tomamos las keywords de la configuración
        'keywords': config_data.get('tools_technologies', []) + config_data.get('job_titles', []) + config_data.get('topics', []),
        'locations': config_data.get('locations', []),
        'max_days_old': config_data.get('scraping', {}).get('date_range_days', 30),
    }

    # Filtrar keywords para tener solo las más relevantes
    # La mejor estrategia: seleccionar algunas de cada categoría
    # y evitar que la lista sea demasiado larga
    search_options['keywords'] = filter_keywords(search_options['keywords'])
    
    # Filtrar ubicaciones para tener solo las más relevantes
    search_options['locations'] = filter_locations(search_options['locations'])

    # Determinamos qué fuentes están habilitadas según settings.yaml
    enabled_sources = get_enabled_sources(config_data, source_types_to_run, sources_to_run)

    # Ejecutamos cada fuente habilitada
    for source_name, source_info in enabled_sources.items():
        source_class = source_info['class']
        source_type = source_info['type']
        source_config = config_data['sources'][source_type][source_name]

        try:
            logger.info(f"Iniciando extracción para {source_name} ({source_type})...")
            source_instance = source_class(http_client=http_client, config=source_config)
            
            # Usar un conjunto limitado de keywords y locations para cada fuente para evitar sobrecarga
            current_search_options = create_search_options_subset(search_options)
            
            # Ejecutamos y obtenemos resultados
            job_offers = source_instance.fetch_jobs(current_search_options)
            
            if job_offers:
                logger.info(f"¡Éxito! Se obtuvieron {len(job_offers)} ofertas de {source_name}.")
                all_job_offers.extend(job_offers)
            else:
                logger.warning(f"No se obtuvieron ofertas de {source_name}.")
                
        except Exception as e:
            logger.error(f"Error al procesar {source_name}: {e}", exc_info=True)
            continue

    # Mostramos resultados
    logger.info(f"Se obtuvieron {len(all_job_offers)} ofertas en total.")
    if all_job_offers:
        # Eliminamos duplicados basados en URL
        unique_offers = remove_duplicates(all_job_offers)
        logger.info(f"Después de eliminar duplicados: {len(unique_offers)} ofertas únicas.")
        
        # Guardamos resultados
        save_results(unique_offers)
        
        # Mostramos algunas ofertas de ejemplo
        show_sample_offers(unique_offers)
    
    return 0

def filter_keywords(keywords):
    """
    Filtra palabras clave para usar un subconjunto representativo.
    Evita búsquedas con demasiadas palabras clave que pueden ser bloqueadas.
    """
    # Eliminar duplicados y normalizar
    unique_keywords = list(set([k.lower().strip() for k in keywords if k and isinstance(k, str)]))
    
    # Limitar el total
    max_keywords = 25
    if len(unique_keywords) > max_keywords:
        # Seleccionamos keywords estratégicamente
        # Combinación de lenguajes, tecnologías y títulos de trabajo
        core_keywords = [
            "python", "javascript", "java", "sql", "react", "node.js", 
            "desarrollador", "developer", "programador", "programmer",
            "full stack", "frontend", "backend", 
            "data", "datos", "engineer", "ingeniero",
            "remoto", "remote", "teletrabajo", "freelance",
            "junior", "trainee", "entry level", "mid level"
        ]
        
        # Filtramos palabras con prioridad a las core_keywords
        filtered = [k for k in unique_keywords if k in core_keywords]
        
        # Añadimos más hasta llegar al límite, si es necesario
        remaining = max_keywords - len(filtered)
        if remaining > 0:
            other_keywords = [k for k in unique_keywords if k not in filtered]
            import random
            filtered.extend(random.sample(other_keywords, min(remaining, len(other_keywords))))
        
        return filtered
    
    return unique_keywords

def filter_locations(locations):
    """
    Filtra ubicaciones para usar un subconjunto representativo.
    """
    # Eliminar duplicados y normalizar
    unique_locations = list(set([loc.strip() for loc in locations if loc and isinstance(loc, str)]))
    
    # Limitar el total
    max_locations = 15
    if len(unique_locations) > max_locations:
        # Priorizar ubicaciones clave para LATAM, España y remote
        priority_locations = [
            "remoto", "remote", "teletrabajo", 
            "españa", "spain", "madrid", "barcelona",
            "méxico", "mexico", "ecuador", "colombia", "perú", "peru", 
            "argentina", "chile", "remote latam"
        ]
        
        # Filtramos ubicaciones con prioridad
        filtered = [loc for loc in unique_locations if loc.lower() in priority_locations]
        
        # Añadimos más hasta llegar al límite, si es necesario
        remaining = max_locations - len(filtered)
        if remaining > 0:
            other_locations = [loc for loc in unique_locations if loc.lower() not in priority_locations]
            import random
            filtered.extend(random.sample(other_locations, min(remaining, len(other_locations))))
        
        return filtered
    
    return unique_locations

def create_search_options_subset(options):
    """
    Crea un subconjunto de opciones de búsqueda para cada fuente.
    Algunas fuentes pueden tener problemas con muchas keywords o locations.
    """
    import random
    
    # Creamos una copia para no modificar el original
    subset = options.copy()
    
    # Limitamos keywords para cada fuente
    max_keywords_per_source = 5
    if 'keywords' in subset and len(subset['keywords']) > max_keywords_per_source:
        subset['keywords'] = random.sample(subset['keywords'], max_keywords_per_source)
    
    # Limitamos locations para cada fuente
    max_locations_per_source = 3
    if 'locations' in subset and len(subset['locations']) > max_locations_per_source:
        subset['locations'] = random.sample(subset['locations'], max_locations_per_source)
    
    return subset

def remove_duplicates(job_offers):
    """Elimina ofertas duplicadas basadas en URL."""
    seen_urls = set()
    unique_offers = []
    
    for offer in job_offers:
        url = offer.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_offers.append(offer)
    
    return unique_offers

def get_enabled_sources(config_data, source_types_to_run=None, sources_to_run=None):
    """
    Determina qué fuentes están habilitadas en la configuración.
    
    Args:
        config_data: Datos de configuración.
        source_types_to_run: Lista de tipos de fuentes a ejecutar ('apis', 'scrapers').
                             Si es None, se ejecutan ambos tipos.
        sources_to_run: Lista de nombres de fuentes específicas a ejecutar.
                        Si es None, se ejecutan todas las habilitadas.
    
    Returns:
        Dict: Diccionario con las fuentes habilitadas.
    """
    enabled_sources = {}
    
    # Determinamos qué tipos de fuentes procesar
    types_to_process = source_types_to_run or ['apis', 'scrapers']
    
    for source_type in types_to_process:
        if source_type not in config_data.get('sources', {}):
            logger.warning(f"Tipo de fuente '{source_type}' no encontrado en la configuración.")
            continue
        
        for source_name, source_config in config_data['sources'][source_type].items():
            # Si especificamos sources_to_run, solo incluimos las que están en la lista
            if sources_to_run and source_name not in sources_to_run:
                continue
                
            # Verificamos si la fuente está habilitada en la configuración
            if source_config.get('enabled', False):
                # Verificamos si tenemos un mapeo para esta fuente
                if source_name in SOURCE_MAP:
                    enabled_sources[source_name] = SOURCE_MAP[source_name]
                else:
                    logger.warning(f"Fuente '{source_name}' habilitada en config pero no implementada en SOURCE_MAP.")
    
    if not enabled_sources:
        logger.warning("No se encontraron fuentes habilitadas que cumplan los criterios.")
    else:
        logger.info(f"Se ejecutarán {len(enabled_sources)} fuentes: {', '.join(enabled_sources.keys())}")
    
    return enabled_sources

def save_results(job_offers):
    """
    Guarda los resultados en la base de datos y/o archivos CSV.
    
    Args:
        job_offers: Lista de ofertas de empleo.
    """
    try:
        # Importamos aquí para no depender de la base de datos si solo mostramos resultados
        from src.persistence.database_manager import DatabaseManager
        from src.persistence.file_exporter import FileExporter
        
        # Guardamos en la base de datos
        db_manager = DatabaseManager(db_path=str(project_root / "data" / "jobs.db"))
        db_manager.save_job_offers(job_offers)
        logger.info(f"Se guardaron {len(job_offers)} ofertas en la base de datos.")
        
        # Exportamos a CSV
        exporter = FileExporter(export_dir=str(project_root / "data" / "historico"))
        csv_path = exporter.export_to_csv(job_offers, include_date=True, prefix="ofertas_todas")
        logger.info(f"Se exportaron las ofertas a: {csv_path}")
        
        # También exportamos un CSV filtrado (ejemplo: solo ofertas remotas)
        remote_offers = [o for o in job_offers if 
                         any(kw in (o.get('titulo', '') + o.get('ubicacion', '')).lower() 
                             for kw in ['remoto', 'remote', 'teletrabajo', 'híbrido', 'hybrid'])]
        
        if remote_offers:
            remote_csv_path = exporter.export_to_csv(remote_offers, include_date=True, prefix="ofertas_remotas")
            logger.info(f"Se exportaron {len(remote_offers)} ofertas remotas a: {remote_csv_path}")
        
        # Exportar ofertas específicas para LATAM/España
        latam_spain_offers = [o for o in job_offers if 
                             any(kw in (o.get('ubicacion', '') + o.get('descripcion', '')).lower() 
                                 for kw in ['españa', 'spain', 'madrid', 'barcelona', 'méxico', 'mexico', 
                                           'colombia', 'ecuador', 'perú', 'peru', 'argentina', 'chile', 
                                           'latam', 'latinoamérica', 'latinoamerica'])]
        
        if latam_spain_offers:
            latam_csv_path = exporter.export_to_csv(latam_spain_offers, include_date=True, prefix="ofertas_latam_spain")
            logger.info(f"Se exportaron {len(latam_spain_offers)} ofertas de LATAM/España a: {latam_csv_path}")
        
    except Exception as e:
        logger.error(f"Error al guardar los resultados: {e}", exc_info=True)

def show_sample_offers(job_offers, limit=5):
    """
    Muestra una muestra de las ofertas obtenidas.
    
    Args:
        job_offers: Lista de ofertas de empleo.
        limit: Número máximo de ofertas a mostrar.
    """
    logger.info("\n--- MUESTRA DE OFERTAS ---")
    
    # Calculamos estadísticas por ubicación
    locations = {}
    for offer in job_offers:
        location = offer.get('ubicacion', 'No especificada').strip()
        if not location:
            location = 'No especificada'
        locations[location] = locations.get(location, 0) + 1
    
    # Mostramos estadísticas de ubicaciones principales
    top_locations = sorted(locations.items(), key=lambda x: x[1], reverse=True)[:10]
    logger.info("Principales ubicaciones:")
    for loc, count in top_locations:
        logger.info(f"  - {loc}: {count} ofertas")
    
    # Mostramos estadísticas por fuente
    sources = {}
    for offer in job_offers:
        source = offer.get('fuente', 'Desconocida').strip()
        sources[source] = sources.get(source, 0) + 1
    
    logger.info("\nFuentes de ofertas:")
    for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  - {source}: {count} ofertas")
    
    # Mostramos algunas ofertas de muestra
    sample = job_offers[:limit]
    logger.info(f"\n{limit} Ofertas de muestra:")
    for i, offer in enumerate(sample, 1):
        logger.info(f"\n[{i}] {offer.get('titulo', 'Sin título')}")
        logger.info(f"    Empresa: {offer.get('empresa', 'No especificada')}")
        logger.info(f"    Ubicación: {offer.get('ubicacion', 'No especificada')}")
        logger.info(f"    Fecha: {offer.get('fecha_publicacion', 'No especificada')}")
        logger.info(f"    URL: {offer.get('url', 'No disponible')}")
        logger.info(f"    Fuente: {offer.get('fuente', 'Desconocida')}")
        # Descripción corta para no saturar la consola
        desc = offer.get('descripcion', 'No disponible')
        if desc and len(desc) > 150:
            desc = desc[:150] + "..."
        logger.info(f"    Descripción: {desc}")

# Punto de entrada del script
if __name__ == "__main__":
    main()