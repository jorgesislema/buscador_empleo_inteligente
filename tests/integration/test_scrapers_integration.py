# -*- coding: utf-8 -*-
# /tests/integration/test_scrapers_integration.py

"""
Pruebas de Integración para los Scrapers Específicos.

Estas pruebas verifican que cada scraper pueda parsear correctamente
un ejemplo de HTML real (guardado localmente como 'fixture') y
extraer los datos esperados en el formato estándar.

NO HACEN PETICIONES HTTP REALES. Usamos monkeypatch para simular
la descarga de HTML leyendo archivos locales de la carpeta /tests/fixtures/.

*** ¡Compañero! Necesitas crear los archivos HTML en /tests/fixtures/ ***
*** para que estas pruebas funcionen. Guarda el código fuente HTML ***
*** de páginas de resultados y detalle reales de cada sitio. ***
"""

import pytest
import sys
from pathlib import Path
import logging
from typing import Dict, Optional

# Añadir raíz para imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Importar lo necesario
try:
    from src.utils.http_client import HTTPClient
    from src.utils import config_loader # Aunque no lo usemos directo, los scrapers sí
    from src.utils import logging_config

    # --- ¡Importar TODAS las clases de Scraper que queremos probar! ---
    from src.scrapers.base_scraper import BaseScraper # Importante para type hints/checks
    from src.scrapers.computrabajo_scraper import ComputrabajoScraper
    from src.scrapers.infojobs_scraper import InfojobsScraper
    from src.scrapers.multitrabajos_scraper import MultitrabajosScraper
    from src.scrapers.porfinempleo_scraper import PorfinempleoScraper
    from src.scrapers.tecnoempleo_scraper import TecnoempleoScraper
    from src.scrapers.empleosnet_scraper import EmpleosNetScraper
    from src.scrapers.portalempleoec_scraper import PortalempleoecScraper
    from src.scrapers.bumeran_scraper import BumeranScraper
    from src.scrapers.getonboard_scraper import GetonboardScraper
    from src.scrapers.remoterocketship_scraper import RemoteRocketshipScraper
    from src.scrapers.workana_scraper import WorkanaScraper
    from src.scrapers.soyfreelancer_scraper import SoyFreelancerScraper
    # ... añadir futuros scrapers aquí ...

except ImportError as e:
     pytest.exit(f"Error importando módulos/clases scraper para pruebas: {e}", returncode=1)

# Configurar logging básico para ver mensajes de las pruebas
# logging_config.setup_logging() # Podríamos configurar el logging real
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constantes y Fixtures ---

# Directorio donde guardaremos/leeremos los HTML de prueba.
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
# ¡Asegúrate de que esta carpeta exista y contenga los HTML!
if not FIXTURES_DIR.is_dir():
    logger.warning(f"Directorio de fixtures no encontrado en {FIXTURES_DIR}. Creándolo.")
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True) # Lo creamos si no existe

# Fixture para tener un cliente HTTP (aunque no hará llamadas reales)
@pytest.fixture(scope="module") # module = una instancia para todas las pruebas de este archivo
def http_client():
    client = HTTPClient()
    yield client
    client.close()

# Fixture para cargar la config una vez (si es necesaria para base_url, etc.)
@pytest.fixture(scope="module")
def app_config():
    try:
        # Forzamos recarga por si acaso
        config_loader._config = None # Resetear config cacheada si la hubiera
        config = config_loader.get_config()
        if not config:
             pytest.fail("No se pudo cargar la configuración necesaria para las pruebas.")
        return config
    except Exception as e:
        pytest.fail(f"Fallo al cargar configuración en fixture: {e}")


# --- Función Genérica para Simular _fetch_html ---

def create_mock_fetch_html(fixture_map: Dict[str, str]):
    """
    Crea una función mock para _fetch_html que lee archivos locales.

    Args:
        fixture_map (Dict[str, str]): Un diccionario donde la clave es una parte
                                     identificativa de la URL esperada y el valor
                                     es el nombre del archivo fixture a leer.

    Returns:
        Callable: La función mock para usar con monkeypatch.
    """
    def mock_fetch(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[str]:
        logger.debug(f"MOCK FETCH: Solicitada URL: {url}")
        # Buscamos qué fixture corresponde a esta URL
        found_fixture = None
        for url_key, filename in fixture_map.items():
            # Hacemos una comprobación simple: si la clave está en la URL solicitada
            if url_key in url:
                found_fixture = filename
                break # Encontramos el primero que coincida

        if found_fixture:
            fixture_path = FIXTURES_DIR / found_fixture
            logger.info(f"MOCK FETCH: URL '{url}' coincide con clave '{url_key}'. Leyendo fixture: {fixture_path}")
            if fixture_path.is_file():
                try:
                    # Leemos el contenido del archivo HTML guardado
                    return fixture_path.read_text(encoding='utf-8')
                except Exception as e:
                     logger.error(f"MOCK FETCH: Error leyendo fixture '{fixture_path}': {e}")
                     return None # Devolver None si no se puede leer el fixture
            else:
                logger.error(f"MOCK FETCH: ¡Fixture file no encontrado! Ruta: {fixture_path}")
                # ¡Fallar la prueba si el fixture no existe es importante!
                pytest.fail(f"Fixture HTML no encontrado: {fixture_path}. Debes crearlo.")
                return None
        else:
            logger.warning(f"MOCK FETCH: URL no mapeada a ningún fixture: {url}")
            # Devolver None si la URL no coincide con ningún fixture conocido para este test
            return None

    return mock_fetch # Devolvemos la función que hará de mock

# --- Pruebas de Integración para Cada Scraper ---

# --- Ejemplo para Computrabajo ---
# ¡Necesitarás crear estos archivos HTML!
COMPUTRABAJO_FIXTURE_MAP = {
    "ofertas-de-trabajo/?q=python+datos&p=Pichincha": "computrabajo_search_results_p1.html", # Pagina 1 resultados
    "/ofertas-de-trabajo/analista-programador/detalle/123ABCDEFG": "computrabajo_detail_1.html", # Ejemplo detalle 1
    "/ofertas-de-trabajo/data-scientist-remoto/detalle/HIJKLMNO": "computrabajo_detail_2.html" # Ejemplo detalle 2
    # Añadir más mapeos si el scraper visita más páginas (ej: paginación)
}

def test_computrabajo_scraper_integration(http_client, monkeypatch, app_config):
    """Prueba la integración del ComputrabajoScraper con HTML de fixture."""
    logger.info("\n--- TEST: test_computrabajo_scraper_integration ---")
    source_name = "computrabajo"
    # Obtenemos la config específica (principalmente por base_url)
    scraper_config = app_config.get('sources', {}).get('scrapers', {}).get(source_name, {})
    if not scraper_config.get('base_url'): pytest.skip(f"Configuración 'base_url' no encontrada para {source_name}")

    # 1. Creamos el scraper
    scraper = ComputrabajoScraper(http_client=http_client, config=scraper_config)

    # 2. Creamos y aplicamos el mock para _fetch_html
    mock_fetch = create_mock_fetch_html(COMPUTRABAJO_FIXTURE_MAP)
    monkeypatch.setattr(scraper, '_fetch_html', mock_fetch.__get__(scraper, type(scraper)))

    # 3. Definimos parámetros de búsqueda (deben coincidir con una clave en el fixture map si afecta la URL)
    search_params = {'keywords': ['python', 'datos'], 'location': 'Quito'} # Asume que esto genera la URL mapeada arriba

    # 4. Ejecutamos fetch_jobs (usará el mock para leer fixtures)
    try:
        jobs = scraper.fetch_jobs(search_params)
    except Exception as e:
        pytest.fail(f"scraper.fetch_jobs lanzó una excepción inesperada: {e}")


    # 5. Verificaciones (Asserts) - ¡Ajustar según el contenido de tus fixtures!
    assert isinstance(jobs, list), "El resultado debería ser una lista."
    # Verificar que obtuvimos *algún* resultado (depende del fixture)
    assert len(jobs) > 0, "La lista de trabajos no debería estar vacía (revisa tu fixture y selectores)."
    # Verificar que cada elemento sea un diccionario
    assert all(isinstance(job, dict) for job in jobs)
    # Verificar que el primer trabajo tenga las claves estándar esperadas y valores no nulos
    first_job = jobs[0]
    assert 'titulo' in first_job and first_job['titulo'] is not None
    assert 'empresa' in first_job # Empresa puede ser None a veces? Verificar
    assert 'url' in first_job and first_job['url'] is not None
    assert 'fuente' in first_job and first_job['fuente'] == source_name
    assert 'descripcion' in first_job # La descripción puede ser None si falla el detalle
    assert 'fecha_publicacion' in first_job
    assert 'ubicacion' in first_job

    # Verificar un valor específico que SEPAS que está en tu fixture HTML
    # EJEMPLO (¡CAMBIAR ESTO!):
    # assert first_job['titulo'] == "Analista Programador Python (De Fixture)"
    # assert "Quito" in first_job['ubicacion'] # O la ubicación esperada
    logger.info(f"Primer trabajo parseado (Computrabajo): {first_job.get('titulo')} - {first_job.get('url')}")


# --- Ejemplo para Infojobs ---
# ¡Necesitarás crear fixtures para Infojobs!
INFOJOBS_FIXTURE_MAP = {
    "list.xhtml?keyword=python+data&page=1": "infojobs_search_p1.html",
     # No visitamos detalle en la versión actual de Infojobs scraper, así que no necesitamos fixtures de detalle.
     # Si modificas el scraper para visitar detalles, necesitarás añadirlos aquí.
}
def test_infojobs_scraper_integration(http_client, monkeypatch, app_config):
    """Prueba la integración del InfojobsScraper con HTML de fixture."""
    logger.info("\n--- TEST: test_infojobs_scraper_integration ---")
    source_name = "infojobs"
    scraper_config = app_config.get('sources', {}).get('scrapers', {}).get(source_name, {})
    if not scraper_config.get('base_url'): pytest.skip(f"Configuración 'base_url' no encontrada para {source_name}")

    scraper = InfojobsScraper(http_client=http_client, config=scraper_config)
    mock_fetch = create_mock_fetch_html(INFOJOBS_FIXTURE_MAP)
    monkeypatch.setattr(scraper, '_fetch_html', mock_fetch.__get__(scraper, type(scraper)))
    search_params = {'keywords': ['python', 'data'], 'location': 'Remote Spain'} # Usar params que generen URL mapeada

    try:
        jobs = scraper.fetch_jobs(search_params)
    except Exception as e:
         pytest.fail(f"scraper.fetch_jobs lanzó una excepción inesperada: {e}")


    assert isinstance(jobs, list)
    assert len(jobs) > 0 # Asumiendo que infojobs_search_p1.html tiene ofertas
    assert all(isinstance(job, dict) for job in jobs)
    first_job = jobs[0]
    assert 'titulo' in first_job and first_job['titulo']
    assert 'url' in first_job and first_job['url']
    assert 'fuente' in first_job and first_job['fuente'] == source_name
    # Verificar otras claves esperadas de Infojobs (empresa, ubicacion, fecha, salario?)
    assert 'empresa' in first_job
    assert 'ubicacion' in first_job
    assert 'fecha_publicacion' in first_job
    assert 'salario' in first_job # Infojobs suele tener salario en la lista

    # EJEMPLO de assert específico (¡CAMBIAR según tu fixture!):
    # assert "€" in first_job['salario'] # Verificar que el salario parece correcto
    logger.info(f"Primer trabajo parseado (Infojobs): {first_job.get('titulo')} - {first_job.get('url')}")


# --- Añadir funciones de test similares para CADA scraper ---
# ej: test_multitrabajos_scraper_integration(...)
#     test_porfinempleo_scraper_integration(...)
#     test_tecnoempleo_scraper_integration(...)
#     test_empleosnet_scraper_integration(...)
#     test_portalempleoec_scraper_integration(...)
#     test_bumeran_scraper_integration(...)
#     test_getonboard_scraper_integration(...)
#     test_remoterocketship_scraper_integration(...)
#     test_workana_scraper_integration(...)
#     test_soyfreelancer_scraper_integration(...)

# --- Ejemplo Vacío para Otro Scraper (Copia y Adapta) ---
# ¡Necesitarás crear fixtures para este scraper!
# OTRAFUENTE_FIXTURE_MAP = {
#     "url_clave_1": "otrafuente_search_p1.html",
#     "url_clave_detalle_1": "otrafuente_detail_1.html",
# }
# def test_otrafuente_scraper_integration(http_client, monkeypatch, app_config):
#     """Prueba la integración del OtroFuenteScraper con HTML de fixture."""
#     logger.info("\n--- TEST: test_otrafuente_scraper_integration ---")
#     source_name = "otrafuente" # Asegúrate que este nombre exista en SOURCE_MAP y settings.yaml
#     # scraper_class = OtrafuenteScraper # Asegúrate de importar la clase correcta
#     scraper_config = app_config.get('sources', {}).get('scrapers', {}).get(source_name, {})
#     if not scraper_config.get('base_url'): pytest.skip(f"Configuración 'base_url' no encontrada para {source_name}")
#
#     # scraper = scraper_class(http_client=http_client, config=scraper_config) # Crear instancia
#     # mock_fetch = create_mock_fetch_html(OTRAFUENTE_FIXTURE_MAP)
#     # monkeypatch.setattr(scraper, '_fetch_html', mock_fetch)
#     # search_params = {'keywords': ['...'], 'location': '...'} # Params relevantes
#
#     # try:
#     #     jobs = scraper.fetch_jobs(search_params)
#     # except Exception as e:
#     #      pytest.fail(f"scraper.fetch_jobs lanzó una excepción inesperada: {e}")
#     #
#     # # --- Asserts ---
#     # assert isinstance(jobs, list)
#     # assert len(jobs) > 0
#     # assert all(isinstance(job, dict) for job in jobs)
#     # first_job = jobs[0]
#     # assert 'titulo' in first_job and first_job['titulo']
#     # assert 'url' in first_job and first_job['url']
#     # assert 'fuente' in first_job and first_job['fuente'] == source_name
#     # # Añadir más asserts específicos para esta fuente basados en el fixture
#     # logger.info(f"Primer trabajo parseado ({source_name}): {first_job.get('titulo')} - {first_job.get('url')}")
#     pytest.skip(f"Prueba para {source_name} aún no implementada con fixtures.") # Saltar si no está lista


# --- Fin de las Pruebas ---