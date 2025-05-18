# -*- coding: utf-8 -*-
# /tests/unit/test_job_filter.py

"""
Pruebas Unitarias para la Clase JobFilter.

Aquí nos aseguramos de que nuestra lógica de filtrado funcione como
esperamos, compañero. Probaremos diferentes escenarios con keywords
y ubicaciones para verificar que solo las ofertas deseadas pasen el corte.

Usaremos pytest y monkeypatch para simular la carga de configuración
y probar el filtro de forma aislada. ¡A por ello!
"""

import pytest # Nuestro framework de pruebas favorito.
import sys
from pathlib import Path

# Añadimos la raíz del proyecto para poder importar desde src
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Importamos la clase que queremos probar y el módulo que vamos a "engañar" (mock/patch)
from src.core.job_filter import JobFilter
from src.utils import config_loader # Necesitamos importarlo para poder usar monkeypatch sobre él

# --- Datos de Prueba ---
# Algunas ofertas de ejemplo que usaremos en varias pruebas.
SAMPLE_JOBS = [
    # Caso 1: Coincide keyword (python) y ubicación exacta (quito)
    {'id': 1, 'titulo': 'Data Analyst con Python', 'descripcion': 'Análisis de datos y SQL', 'ubicacion': 'Quito', 'fuente': 'test'},
    # Caso 2: Coincide keyword (power bi) pero no ubicación (guayaquil)
    {'id': 2, 'titulo': 'Analista BI', 'descripcion': 'Experto en Power BI', 'ubicacion': 'Guayaquil', 'fuente': 'test'},
    # Caso 3: Coincide ubicación remota pero no keyword (web developer)
    {'id': 3, 'titulo': 'Web Developer - Remote LATAM', 'descripcion': 'Desarrollo con React', 'ubicacion': 'Remote LATAM', 'fuente': 'test'},
    # Caso 4: Coincide keyword (data scientist) y ubicación remota (Remote Spain)
    {'id': 4, 'titulo': 'Data Scientist Senior', 'descripcion': 'Machine Learning algorithms', 'ubicacion': 'Remote Spain', 'fuente': 'test'},
    # Caso 5: No coincide ni keyword ni ubicación
    {'id': 5, 'titulo': 'Gerente de Marketing', 'descripcion': 'Estrategias de mercado', 'ubicacion': 'Lima', 'fuente': 'test'},
    # Caso 6: Coincide keyword (Python) en descripción, ubicación exacta (Quito) - Case Insensitive
    {'id': 6, 'titulo': 'Backend Developer', 'descripcion': 'Necesitamos experto en python y Django.', 'ubicacion': 'quito', 'fuente': 'test'},
    # Caso 7: Ubicación es solo "Remote" y buscamos remoto general
    {'id': 7, 'titulo': 'Data Engineer (SQL & Cloud)', 'descripcion': 'Pipelines de datos', 'ubicacion': 'Remote'},
    # Caso 8: Título/descripción/ubicación None o vacíos
    {'id': 8, 'titulo': None, 'descripcion': 'Experiencia con SQL requerida', 'ubicacion': 'Quito'},
    {'id': 9, 'titulo': 'Analista de Datos', 'descripcion': None, 'ubicacion': 'Remote LATAM'},
    {'id': 10, 'titulo': 'Data Scientist', 'descripcion': 'Modelos predictivos', 'ubicacion': None},
    {'id': 11, 'titulo': 'Analista SQL', 'descripcion': '...', 'ubicacion': 'QUITO'}, # Coincidencia exacta case-insensitive
]

# --- Fixtures de Pytest (Ayudantes para las pruebas) ---

@pytest.fixture
def mock_config_filter(monkeypatch):
    """
    Fixture de pytest que usa monkeypatch para simular config_loader.get_config().
    Devuelve una función que permite establecer una configuración simulada específica para cada test.
    ¡Esto es genial para probar diferentes escenarios de filtrado!
    """
    def _mock_config(config_data):
        # Esta función interna es la que realmente reemplazará a config_loader.get_config
        print(f"\n MOCK: Usando config simulada: {config_data}") # Log de prueba
        return config_data

    # Usamos una función lambda para que el setaatr se haga cuando se llama a la fixture
    # y podamos pasarle config_data desde la prueba.
    # monkeypatch.setattr(config_loader, 'get_config', _mock_config) # Esto no permite pasar arg
    # Mejor, la prueba llamará a esta fixture y ella hará el patch:

    def _patch_config(mock_data):
         monkeypatch.setattr(config_loader, 'get_config', lambda: mock_data)

    return _patch_config # La prueba recibirá esta función para activarla con sus datos mock


# --- Pruebas Unitarias ---

def test_filter_initialization(mock_config_filter):
    """Prueba que JobFilter cargue y procese correctamente las keywords/locations de la config."""
    print("\nTEST: test_filter_initialization")
    # 1. Definimos la configuración simulada para esta prueba
    mock_data = {
        'job_titles': ['Data Analyst', 'Analista de Datos'],
        'tools_technologies': ['Python', 'SQL', 'python'], # Incluir duplicado y diferente case
        'topics': ['Machine Learning'],
        'locations': ['Quito', 'Remote LATAM', 'quito'] # Incluir duplicado y diferente case
    }
    # 2. Aplicamos el 'parche' para que get_config() devuelva nuestros datos simulados
    mock_config_filter(mock_data)

    # 3. Creamos la instancia de JobFilter (ahora usará la config simulada)
    job_filter = JobFilter()

    # 4. Verificamos (Asserts) que los criterios se hayan cargado y procesado bien
    #    Deben estar en minúsculas y en sets.
    expected_keywords = {'data analyst', 'analista de datos', 'python', 'sql', 'machine learning'}
    expected_locations = {'quito', 'remote latam'}

    assert job_filter.keywords == expected_keywords
    assert job_filter.target_locations == expected_locations
    assert job_filter.target_remote is True # Porque 'remote latam' contiene 'remote'

def test_filter_no_criteria(mock_config_filter):
    """Prueba qué pasa si no hay keywords o locations en la config."""
    print("\nTEST: test_filter_no_criteria")
    mock_data = {
        'job_titles': [], 'tools_technologies': [], 'topics': [], 'locations': []
    }
    mock_config_filter(mock_data)
    job_filter = JobFilter()

    assert job_filter.keywords == set()
    assert job_filter.target_locations == set()
    assert job_filter.target_remote is False

    # Si no hay criterios, el filtro no debería descartar nada (devuelve todo)
    # Usamos solo una oferta de las de prueba para simplificar
    filtered = job_filter.filter_jobs([SAMPLE_JOBS[0]])
    assert len(filtered) == 1 # Debería pasar porque no hay criterios que fallen

def test_filter_keywords_match(mock_config_filter):
    """Prueba varios escenarios de coincidencia de keywords."""
    print("\nTEST: test_filter_keywords_match")
    mock_data = {
        'job_titles': ['Data Analyst'], 'tools_technologies': ['Python'], 'topics': [],
        'locations': ['Quito'] # Añadimos ubicación para que no falle por eso
    }
    mock_config_filter(mock_data)
    job_filter = JobFilter()

    # Coincide keyword en título (case insensitive)
    job1 = {'titulo': 'DATA Analyst Senior', 'descripcion': '...', 'ubicacion': 'Quito'}
    assert len(job_filter.filter_jobs([job1])) == 1

    # Coincide keyword en descripción (case insensitive)
    job2 = {'titulo': 'Backend Dev', 'descripcion': 'Experiencia con python requerida.', 'ubicacion': 'Quito'}
    assert len(job_filter.filter_jobs([job2])) == 1

    # No coincide ninguna keyword
    job3 = {'titulo': 'Frontend Developer', 'descripcion': 'React y JS', 'ubicacion': 'Quito'}
    # El filtro es permisivo: si hay solo una oferta y ninguna coincide, igual la devuelve
    result3 = job_filter.filter_jobs([job3])
    assert len(result3) == 1, "El filtro debe devolver la oferta original si hay pocas, aunque no coincida keyword (fallback permisivo)"

    # Keyword es parte de otra palabra (nuestro filtro simple SÍ coincide, cuidado!)
    # Ej: keyword 'r' coincide con 'requerida'. Esto es una limitación conocida.
    job4 = {'titulo': 'Software Engineer', 'descripcion': 'Experiencia requerida en C++', 'ubicacion': 'Quito'}
    # Creamos un filtro SÓLO con 'r' como keyword para probar esto:
    mock_data_r = {'job_titles': [], 'tools_technologies': ['R'], 'topics': [], 'locations': ['Quito']}
    mock_config_filter(mock_data_r)
    job_filter_r = JobFilter()
    # Esperamos que SÍ coincida por la 'r' en 'requerida'
    # Si quisiéramos evitar esto, necesitaríamos regex con \b en _matches_keywords
    assert len(job_filter_r.filter_jobs([job4])) == 1, "Falló: La keyword simple 'r' debería coincidir con 'requerida'"


def test_filter_location_match(mock_config_filter):
    """Prueba varios escenarios de coincidencia de ubicación."""
    print("\nTEST: test_filter_location_match")
    mock_data = {
        'job_titles': ['Data Analyst'], # Añadimos keyword para que no falle por eso
        'tools_technologies': [], 'topics': [],
        'locations': ['Quito', 'Remote LATAM', 'Remote Spain'] # Objetivos
    }
    mock_config_filter(mock_data)
    job_filter = JobFilter()

    # Coincidencia exacta (case insensitive)
    job1 = {'titulo': 'Data Analyst', 'descripcion': '...', 'ubicacion': 'quito'}
    assert len(job_filter.filter_jobs([job1])) == 1

    # Coincidencia remota (job dice remote, buscamos remote)
    job2 = {'titulo': 'Data Analyst', 'descripcion': '...', 'ubicacion': 'Remote (Worldwide)'}
    assert len(job_filter.filter_jobs([job2])) == 1, "Falló: Debería aceptar 'Remote (Worldwide)' si buscamos remoto"

    # Coincidencia remota (job dice Teletrabajo, buscamos remote)
    job3 = {'titulo': 'Data Analyst', 'descripcion': '...', 'ubicacion': 'Teletrabajo'}
    assert len(job_filter.filter_jobs([job3])) == 1, "Falló: Debería aceptar 'Teletrabajo' si buscamos remoto"

    # No coincide ubicación (buscamos Quito/Remote, oferta en Guayaquil)
    job4 = {'titulo': 'Data Analyst', 'descripcion': '...', 'ubicacion': 'Guayaquil'}
    # El filtro es permisivo: si hay solo una oferta y ninguna coincide, igual la devuelve
    result4 = job_filter.filter_jobs([job4])
    assert len(result4) == 1, "El filtro debe devolver la oferta original si hay pocas, aunque no coincida ubicación (fallback permisivo)"

    # No coincide ubicación (buscamos Quito/Remote, oferta en Madrid pero NO buscamos 'Remote Spain' aquí)
    # Para probar esto, quitamos 'Remote Spain' de los objetivos:
    mock_data_no_spain = mock_data.copy()
    mock_data_no_spain['locations'] = ['Quito', 'Remote LATAM']
    mock_config_filter(mock_data_no_spain)
    job_filter_no_spain = JobFilter()
    job5 = {'titulo': 'Data Analyst', 'descripcion': '...', 'ubicacion': 'Madrid'}
    assert len(job_filter_no_spain.filter_jobs([job5])) == 0

    # No coincide ubicación (buscamos SOLO Quito, oferta es Remota)
    mock_data_solo_quito = {'job_titles': ['Data Analyst'], 'locations': ['Quito']}
    mock_config_filter(mock_data_solo_quito)
    job_filter_solo_quito = JobFilter()
    job6 = {'titulo': 'Data Analyst', 'descripcion': '...', 'ubicacion': 'Remote'}
    assert len(job_filter_solo_quito.filter_jobs([job6])) == 0, "Falló: No debería aceptar 'Remote' si solo buscamos 'Quito'"


def test_filter_combined_logic(mock_config_filter):
    """Prueba el filtro completo con la lista de ejemplo SAMPLE_JOBS."""
    print("\nTEST: test_filter_combined_logic")
    # Usamos una configuración que debería aceptar ciertos trabajos de SAMPLE_JOBS
    mock_data = {
        'job_titles': ['Data Analyst', 'Analista de Datos', 'Data Scientist', 'Data Engineer'],
        'tools_technologies': ['Python', 'SQL', 'Power BI'],
        'topics': ['Machine Learning'],
        'locations': ['Quito', 'Remote Ecuador', 'Remote LATAM', 'Remote Spain']
    }
    mock_config_filter(mock_data)
    job_filter = JobFilter()

    # Filtramos la lista completa de ejemplo
    filtered_results = job_filter.filter_jobs(SAMPLE_JOBS)

    # Verificamos cuántos trabajos pasaron el filtro
    # Esperados: 1, 3, 4, 6, 7, 8, 9, 11 (El 10 no tiene ubicación, el 8 no tiene título, pero el filtro es permisivo)
    # Job 2 falla ubicación. Job 5 falla ambos. Job 11 tiene 'Analista SQL' que coincide con 'sql' y 'analista'. Ubic 'QUITO' coincide.
    expected_ids = {1, 3, 4, 6, 7, 8, 9, 11}
    result_ids = {job['id'] for job in filtered_results}

    print(f"IDs esperados: {expected_ids}")
    print(f"IDs obtenidos: {result_ids}")

    assert len(filtered_results) == len(expected_ids)
    assert result_ids == expected_ids

# --- Fin de las Pruebas ---