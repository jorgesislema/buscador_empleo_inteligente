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
    """Función principal del script."""

    # --- Configurar y Parsear Argumentos ---
    parser = argparse.ArgumentParser(
        description="Ejecuta un scraper o cliente API específico para probarlo.",
        formatter_class=argparse.RawTextHelpFormatter # Para mostrar mejor la ayuda
    )
    parser.add_argument(
        "source_name",
        help="El nombre de la fuente a ejecutar (clave de settings.yaml).",
        choices=SOURCE_MAP.keys(), # Solo permite nombres que tengamos mapeados
        metavar="nombre_fuente" # Nombre que se muestra en la ayuda
    )
    # Podríamos añadir más argumentos aquí:
    # parser.add_argument("-k", "--keywords", help="Palabras clave (separadas por coma)")
    # parser.add_argument("-l", "--location", help="Ubicación")
    # parser.add_argument("-p", "--pages", type=int, default=1, help="Número máximo de páginas a procesar")

    args = parser.parse_args()
    source_to_run = args.source_name
    print(f"--- Ejecutando Fuente Manualmente: {source_to_run} ---")

    # --- Configuraciones Iniciales ---
    try:
        logging_config.setup_logging() # Configurar logging según settings.yaml
        config = config_loader.get_config() # Cargar toda la configuración
        if not config:
             logger.error("No se pudo cargar la configuración general (settings.yaml). Abortando.")
             return # Salir si no hay config
    except Exception as e:
        logger.exception(f"Error crítico durante la configuración inicial: {e}")
        return # Salir si falla la configuración

    # Creamos nuestro cliente HTTP reutilizable
    http_client = HTTPClient()

    try:
        # --- Preparar la Fuente Específica ---
        if source_to_run not in SOURCE_MAP:
            # Esto no debería pasar gracias a 'choices' en argparse, pero por si acaso.
            logger.error(f"Nombre de fuente '{source_to_run}' no reconocido.")
            return

        source_info = SOURCE_MAP[source_to_run]
        SourceClass = source_info["class"] # La clase a instanciar (ej: ComputrabajoScraper)
        source_type = source_info["type"]  # 'apis' o 'scrapers'

        # Obtenemos la configuración específica para esta fuente desde settings.yaml
        source_config = config.get('sources', {}).get(source_type, {}).get(source_to_run, {})
        if not source_config:
            logger.warning(f"No se encontró configuración específica para '{source_to_run}' en settings.yaml bajo 'sources.{source_type}'.")
            # Podemos decidir continuar con config vacía o abortar. Continuemos por ahora.
            # return

        # Verificamos si está habilitada en la config (aunque aquí la forzamos a correr)
        is_enabled = source_config.get('enabled', False)
        if not is_enabled:
             logger.warning(f"La fuente '{source_to_run}' está marcada como 'enabled: false' en settings.yaml, pero se ejecutará igualmente por petición manual.")


        # --- Instanciar y Ejecutar ---
        logger.info(f"Instanciando {SourceClass.__name__}...")
        try:
            # Creamos la instancia pasándole el cliente http y su config específica.
            instance = SourceClass(http_client=http_client, config=source_config)
        except Exception as e:
             logger.exception(f"Error al instanciar la clase {SourceClass.__name__}: {e}")
             return

        # Definimos parámetros de búsqueda para esta prueba manual.
        # ¡Puedes cambiar esto para probar diferentes búsquedas!
        test_search_params = {
            'keywords': ['python', 'datos'], # Keywords de prueba
            'location': 'Quito'             # Ubicación de prueba (ajustar según la fuente)
            # 'page': 1 # El fetch_jobs usualmente maneja la paginación interna, no se pasa aquí.
        }
        logger.info(f"Ejecutando fetch_jobs con parámetros de prueba: {test_search_params}")

        # ¡Llamamos al método principal de la instancia!
        results = instance.fetch_jobs(test_search_params)

        # --- Mostrar Resultados ---
        if results is None:
             logger.error("La función fetch_jobs devolvió None. Hubo un error durante la ejecución.")
        else:
            logger.info(f"Ejecución completada. Se encontraron {len(results)} ofertas/proyectos.")
            if results:
                # Imprimimos las primeras 3 ofertas (o menos si hay menos) para verlas.
                print("\n--- Primeros Resultados Encontrados ---")
                pprint.pprint(results[:3])
                if len(results) > 3:
                    print(f"\n(Mostrando 3 de {len(results)} resultados...)")
            else:
                print("\nNo se encontraron resultados con los parámetros de prueba.")

    except Exception as e:
        logger.exception(f"Ocurrió un error inesperado al ejecutar la fuente '{source_to_run}': {e}")
    finally:
        # ¡Importante! Cerramos el cliente HTTP al final para liberar recursos.
        if 'http_client' in locals() and http_client:
            http_client.close()
        print(f"\n--- Ejecución Manual Finalizada: {source_to_run} ---")


# Punto de entrada del script
if __name__ == "__main__":
    main()