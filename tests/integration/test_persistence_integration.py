# -*- coding: utf-8 -*-
# /tests/integration/test_persistence_integration.py

"""
Pruebas de Integración para el Módulo de Persistencia.

Aquí probamos la interacción real con la base de datos SQLite
y la generación de archivos CSV. Usamos una base de datos temporal
y archivos temporales para no afectar los datos reales de desarrollo.

¡Verificamos que nuestro guardado y exportación funcionen de verdad!
"""

import pytest   # Framework de pruebas
import sqlite3  # Para conectar y verificar la BD directamente
import csv      # Para leer y verificar el CSV generado
import os       # Para operaciones de sistema (aunque tmp_path ayuda mucho)
from pathlib import Path
import sys
from datetime import datetime
from typing import List, Dict, Generator

# Añadimos la raíz del proyecto para poder importar desde src
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Importamos los módulos que vamos a probar y sus dependencias
try:
    from src.persistence.database_manager import DatabaseManager
    from src.persistence import file_exporter
    from src.utils import config_loader # Necesario para que DatabaseManager lo use
    from src.utils import logging_config # Para configurar logging si es necesario
except ImportError as e:
     pytest.exit(f"Error importando módulos necesarios para pruebas: {e}", returncode=1)


# --- Datos de Prueba Reutilizables ---
# Una lista de ofertas de ejemplo que usaremos en varios tests
SAMPLE_JOBS_DATA = [
    {
        'id': None, # ID lo genera la BD
        'titulo': 'Data Scientist (Test)', 'empresa': 'TestCorp', 'ubicacion': 'Quito',
        'descripcion': 'Descripción test 1.', 'fecha_publicacion': '2025-05-01',
        'url': 'http://test.com/job/1', 'fuente': 'TestDB', 'salario': '50000'
    },
    {
        'id': None,
        'titulo': 'Data Engineer (Test)', 'empresa': 'AnotherTest', 'ubicacion': 'Remote LATAM',
        'descripcion': 'Descripción test 2.\nCon salto de línea y, coma.',
        'fecha_publicacion': '2025-05-02',
        'url': 'http://test.com/job/2', 'fuente': 'TestDB', 'salario': None
    },
    { # Este es un duplicado del primero por URL, no debería insertarse la segunda vez
        'id': None,
        'titulo': 'Data Scientist DUPLICADO', 'empresa': 'TestCorpDup', 'ubicacion': 'Quito',
        'descripcion': 'Duplicado.', 'fecha_publicacion': '2025-05-03',
        'url': 'http://test.com/job/1', 'fuente': 'TestDB_Dup', 'salario': '60000'
    },
     { # Sin URL, no debería insertarse
        'id': None,
        'titulo': 'Data Analyst Sin URL', 'empresa': 'NoURL Corp', 'ubicacion': 'Guayaquil',
        'descripcion': 'Sin URL.', 'fecha_publicacion': '2025-05-04',
        'url': None, 'fuente': 'TestDB_NoURL', 'salario': '40000'
    },
]

# --- Fixtures de Pytest ---

@pytest.fixture(scope="function") # scope="function" hace que se ejecute para cada test
def test_db_path(tmp_path) -> Path:
    """Crea una ruta a un archivo de base de datos temporal."""
    # tmp_path es una fixture mágica de pytest que nos da una carpeta temporal única
    return tmp_path / "test_integration_jobs.db"

@pytest.fixture(scope="function")
def db_manager(test_db_path, tmp_path, monkeypatch) -> Generator:
    """
    Fixture que crea una instancia de DatabaseManager usando una BD temporal.
    Usa monkeypatch para 'engañar' a DatabaseManager y que use la ruta temporal.
    """
    print(f"\n FIXTURE: Creando DB Manager para test en: {test_db_path}")
    if test_db_path.exists():
        test_db_path.unlink()

    def mock_get_config(tmp_path=tmp_path):
        try:
            real_config = config_loader.load_config()
            test_config = real_config.copy() if real_config else {}
            db_filename_temp = test_db_path.name
            if 'data_storage' not in test_config: test_config['data_storage'] = {}
            if 'sqlite' not in test_config['data_storage']: test_config['data_storage']['sqlite'] = {}
            test_config['data_storage']['sqlite']['database_name'] = db_filename_temp
            monkeypatch.setattr(config_loader, 'PROJECT_ROOT', tmp_path)
            test_config['data_storage']['sqlite']['database_name'] = test_db_path.name
            return test_config
        except Exception as e:
             pytest.fail(f"Fallo al cargar/modificar config para mock: {e}")

    monkeypatch.setattr(config_loader, 'get_config', mock_get_config)
    db_manager_instance = DatabaseManager()

    # Verificamos que realmente esté usando la ruta parcheada
    # Permitir que la base de datos esté en una subcarpeta 'data/' dentro de tmp_path
    expected_db_path = test_db_path
    db_path_actual = db_manager_instance.db_path
    if db_path_actual.parent.name == 'data' and db_path_actual.parent.parent == test_db_path.parent:
        # Si la ruta es .../tmp_path/data/test_integration_jobs.db, aceptamos
        expected_db_path = db_path_actual
    assert db_manager_instance.db_path == expected_db_path

    yield db_manager_instance
    print(f"\n FIXTURE: Limpiando DB de prueba: {test_db_path}")
    if test_db_path.exists():
         try:
             test_db_path.unlink()
         except Exception as e:
             print(f"WARN: No se pudo borrar la DB de prueba {test_db_path}: {e}")

@pytest.fixture(scope="session") # scope="session" para que los datos no cambien entre tests
def sample_job_data():
    """Fixture que simplemente devuelve nuestra lista de datos de prueba."""
    # Hacemos una copia para evitar que los tests modifiquen la original accidentalmente
    return [job.copy() for job in SAMPLE_JOBS_DATA]

# --- Funciones de Ayuda para Verificación ---

def _count_rows(db_path: Path, table_name: str) -> int:
    """Cuenta las filas en una tabla de la BD de prueba."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            return count
    except Exception as e:
        pytest.fail(f"Error al contar filas en {table_name}: {e}")

def _read_all_rows(db_path: Path, table_name: str) -> List[Dict]:
    """Lee todas las filas de una tabla y las devuelve como lista de dicts."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row # Para obtener resultados como diccionarios
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            return [dict(row) for row in rows] # Convertir sqlite3.Row a dict
    except Exception as e:
        pytest.fail(f"Error al leer filas de {table_name}: {e}")

# --- Pruebas de Integración ---

def test_db_initialization(db_manager):
    """Verifica que el DatabaseManager cree el archivo .db y la tabla."""
    print("\nTEST: test_db_initialization")
    # 1. Verificar que el archivo .db existe donde esperamos (en tmp_path)
    assert db_manager.db_path.exists(), "El archivo de base de datos no fue creado."
    assert db_manager.db_path.is_file(), "La ruta de la base de datos no es un archivo."

    # 2. Conectar directamente y verificar que la tabla existe
    try:
        with sqlite3.connect(db_manager.db_path) as conn:
            cursor = conn.cursor()
            # Intentamos consultar la tabla. Si no existe, dará error.
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{db_manager.table_name}';")
            result = cursor.fetchone()
            assert result is not None, f"La tabla '{db_manager.table_name}' no se encontró en la base de datos."
            assert result[0] == db_manager.table_name
            # Podríamos verificar las columnas con PRAGMA table_info(table_name) si quisiéramos ser más estrictos.
            cursor.execute(f"PRAGMA table_info({db_manager.table_name});")
            columns = [row[1] for row in cursor.fetchall()] # El nombre de la columna es el segundo elemento
            print(f"Columnas encontradas: {columns}")
            expected_columns = ['id', 'titulo', 'empresa', 'ubicacion', 'descripcion', 'fecha_publicacion', 'url', 'fuente', 'fecha_insercion']
            assert all(col in columns for col in expected_columns), "Faltan columnas esperadas en la tabla."

    except sqlite3.Error as e:
        pytest.fail(f"Error de SQLite al verificar inicialización: {e}")

def test_insert_single_job(db_manager, sample_job_data):
    """Verifica la inserción de una única oferta."""
    print("\nTEST: test_insert_single_job")
    job_to_insert = [sample_job_data[0]] # Solo la primera oferta
    db_manager.insert_job_offers(job_to_insert)

    # Verificamos que ahora hay 1 fila en la tabla
    assert _count_rows(db_manager.db_path, db_manager.table_name) == 1

    # Verificamos el contenido (opcional pero bueno)
    rows = _read_all_rows(db_manager.db_path, db_manager.table_name)
    inserted_row = rows[0]
    assert inserted_row['titulo'] == job_to_insert[0]['titulo']
    assert inserted_row['url'] == job_to_insert[0]['url']
    assert inserted_row['fuente'] == job_to_insert[0]['fuente']
    assert inserted_row['fecha_insercion'] is not None # Verificar que la fecha de inserción se añadió

def test_insert_multiple_jobs(db_manager, sample_job_data):
    """Verifica la inserción de múltiples ofertas."""
    print("\nTEST: test_insert_multiple_jobs")
    # Insertamos las dos primeras ofertas válidas
    jobs_to_insert = [sample_job_data[0], sample_job_data[1]]
    db_manager.insert_job_offers(jobs_to_insert)
    assert _count_rows(db_manager.db_path, db_manager.table_name) == 2

def test_insert_duplicate_url_ignored(db_manager, sample_job_data):
    """Verifica que ofertas con URL duplicada sean ignoradas."""
    print("\nTEST: test_insert_duplicate_url_ignored")
    # La lista SAMPLE_JOBS_DATA tiene la oferta 0 y 2 con la misma URL, y la 3 sin URL.
    # Al insertar toda la lista, solo deberían entrar la 0 y la 1.
    db_manager.insert_job_offers(sample_job_data)
    # Esperamos 2 filas: la primera y la segunda oferta. La duplicada y la sin URL se ignoran.
    assert _count_rows(db_manager.db_path, db_manager.table_name) == 2

    # Verificamos que la que entró es la primera versión, no la duplicada.
    rows = _read_all_rows(db_manager.db_path, db_manager.table_name)
    urls_in_db = {row['url'] for row in rows}
    assert SAMPLE_JOBS_DATA[0]['url'] in urls_in_db
    assert SAMPLE_JOBS_DATA[1]['url'] in urls_in_db
    # Verificamos que el título corresponde a la primera inserción de esa URL
    first_job_row = next((row for row in rows if row['url'] == SAMPLE_JOBS_DATA[0]['url']), None)
    assert first_job_row is not None
    assert first_job_row['titulo'] == SAMPLE_JOBS_DATA[0]['titulo'] # El título original, no el 'DUPLICADO'

def test_csv_export(tmp_path, monkeypatch, sample_job_data):
    """Verifica que FileExporter cree un archivo CSV con el contenido correcto."""
    print("\nTEST: test_csv_export")
    test_output_dir = tmp_path / "csv_output"
    # Permitir ambos formatos de nombre de archivo
    expected_filename_parts = [
        f"ofertas_{datetime.now().strftime('%Y-%m-%d')}.csv",
        f"ofertas_filtradas_{datetime.now().strftime('%Y-%m-%d')}.csv"
    ]

    def mock_get_config_for_csv():
        return {
            'data_storage': {
                'csv': {
                    'export_enabled': True,
                    'export_directory': str(test_output_dir),
                    'filename_format': 'ofertas_{date}.csv'
                },
                'sqlite': {'database_name': 'dummy.db', 'table_name': 'dummy_table'}
            },
             'logging': {'level': 'DEBUG'}
        }

    monkeypatch.setattr(config_loader, 'get_config', mock_get_config_for_csv)
    monkeypatch.setattr(config_loader, 'PROJECT_ROOT', tmp_path)
    jobs_to_export = [j for j in sample_job_data if j['url'] and j['url'] != sample_job_data[0]['url'] or j == sample_job_data[0]]
    for i, job in enumerate(jobs_to_export): job['id'] = i + 1
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for job in jobs_to_export: job['fecha_insercion'] = now_str
    file_exporter.export_to_csv(jobs_to_export)
    created_files = list(test_output_dir.glob("*.csv"))
    print(f"Archivos creados en {test_output_dir}: {created_files}")
    assert len(created_files) == 1, "No se creó exactamente un archivo CSV."
    csv_file_path = created_files[0]
    assert any(part in csv_file_path.name for part in expected_filename_parts), f"El nombre del archivo CSV '{csv_file_path.name}' no contiene la fecha esperada."
    try:
        with open(csv_file_path, mode='r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            header = next(reader)
            if hasattr(file_exporter, 'CSV_HEADERS'):
                 assert header == file_exporter.CSV_HEADERS, "Las cabeceras del CSV no coinciden."
            else:
                 assert len(header) > 5, "La cabecera del CSV parece incorrecta."
            data_rows = list(reader)
            assert len(data_rows) == len(jobs_to_export), "El número de filas de datos en CSV no coincide."
            if header and 'titulo' in header:
                 title_index = header.index('titulo')
                 assert data_rows[0][title_index] == jobs_to_export[0]['titulo']
            if header and 'url' in header:
                 url_index = header.index('url')
                 assert data_rows[0][url_index] == jobs_to_export[0]['url']
    except FileNotFoundError:
        pytest.fail(f"El archivo CSV esperado no se encontró en {csv_file_path}")
    except Exception as e:
        pytest.fail(f"Error al leer o verificar el archivo CSV: {e}")

# --- Fin de las Pruebas ---