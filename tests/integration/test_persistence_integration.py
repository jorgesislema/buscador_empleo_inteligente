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
def db_manager(test_db_path, monkeypatch) -> DatabaseManager:
    """
    Fixture que crea una instancia de DatabaseManager usando una BD temporal.
    Usa monkeypatch para 'engañar' a DatabaseManager y que use la ruta temporal.
    """
    print(f"\n FIXTURE: Creando DB Manager para test en: {test_db_path}")
    # Asegurarnos de que el archivo no exista de una prueba anterior si algo falló
    if test_db_path.exists():
        test_db_path.unlink()

    # Engañamos al DatabaseManager para que use nuestra ruta temporal.
    # Hacemos esto ANTES de instanciarlo. Podríamos parchear config_loader o
    # la propiedad db_path directamente si fuera necesario y más fácil.
    # Parcheamos la propiedad directamente después de la inicialización inicial
    # que usa la config real (pero crea la tabla en nuestra DB temporal).

    # Opción 1: Parchear la propiedad db_path DESPUÉS de que __init__ la calcule.
    # db_manager_instance = DatabaseManager() # Llama a _initialize_database con la ruta REAL (¡cuidado!)
    # monkeypatch.setattr(db_manager_instance, 'db_path', test_db_path)
    # # Tendríamos que llamar a _initialize_database de nuevo con la ruta parcheada.
    # db_manager_instance._initialize_database() # ¡Esto podría no ser ideal si init hace más cosas!

    # Opción 2: Parchear config_loader para que devuelva la ruta temporal. ¡Más limpio!
    def mock_get_config():
        # Devolvemos una config mínima simulada SÓLO con la ruta de la BD cambiada
        # ¡Ojo! Esto significa que el nombre de la tabla y otras configs serán las reales.
        # Si necesitamos aislar más, copiamos la config real y modificamos sólo la ruta.
        try:
            real_config = config_loader.load_config() # Carga la real una vez
            test_config = real_config.copy() if real_config else {} # Copia superficial
            # Modificamos SÓLO lo necesario para apuntar a la BD de prueba
            db_filename_temp = test_db_path.name
            # Asumimos la estructura data_storage -> sqlite -> database_name
            if 'data_storage' not in test_config: test_config['data_storage'] = {}
            if 'sqlite' not in test_config['data_storage']: test_config['data_storage']['sqlite'] = {}
            test_config['data_storage']['sqlite']['database_name'] = db_filename_temp
            # ¡IMPORTANTE! Necesitamos que se guarde en la carpeta tmp_path, no en data/
            # Modificamos PROJECT_ROOT temporalmente para que DatabaseManager construya bien la ruta.
            monkeypatch.setattr(config_loader, 'PROJECT_ROOT', tmp_path) # Apuntar a la carpeta temporal
            # Y aseguramos que el nombre del archivo sea el nuestro
            test_config['data_storage']['sqlite']['database_name'] = test_db_path.name

            return test_config
        except Exception as e:
             pytest.fail(f"Fallo al cargar/modificar config para mock: {e}")

    # Aplicamos el parche a la función que usa DatabaseManager
    # ¡Ojo! Si DatabaseManager importa get_config con 'from src.utils.config_loader import get_config',
    # hay que parchear EN DatabaseManager, no en config_loader.
    # Asumiendo que hace 'from src.utils import config_loader' y llama a 'config_loader.get_config()':
    monkeypatch.setattr(config_loader, 'get_config', mock_get_config)

    # Ahora sí, creamos la instancia. Usará la config modificada por el monkeypatch.
    # Su __init__ llamará a _initialize_database() y creará la tabla en test_db_path.
    db_manager_instance = DatabaseManager()
    # Verificamos que realmente esté usando la ruta parcheada
    assert db_manager_instance.db_path == test_db_path

    # Retornamos la instancia lista para usar en las pruebas
    yield db_manager_instance

    # --- Limpieza (Teardown) ---
    # Monkeypatch se revierte solo. tmp_path se limpia solo.
    # Pero si quisiéramos borrar el archivo manualmente:
    print(f"\n FIXTURE: Limpiando DB de prueba: {test_db_path}")
    if test_db_path.exists():
         try:
             # A veces la conexión puede quedar abierta si algo falló, cerramos forzosamente? No, confiamos en 'with'.
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
    # Usamos la fixture tmp_path directamente para la salida del CSV.
    test_output_dir = tmp_path / "csv_output"
    expected_filename_part = f"ofertas_{datetime.now().strftime('%Y-%m-%d')}.csv" # Asumiendo formato default

    # 1. Engañar a file_exporter para que use nuestro directorio temporal y esté habilitado.
    #    Necesitamos parchear config_loader ANTES de llamar a export_to_csv.
    def mock_get_config_for_csv():
        # Devolver una config mínima simulada que HABILITE y redirija CSV
        return {
            'data_storage': {
                'csv': {
                    'export_enabled': True,
                    'export_directory': str(test_output_dir.relative_to(project_root)), # Ruta relativa a la raíz simulada
                    'filename_format': 'ofertas_{date}.csv'
                },
                # Incluir sección sqlite dummy por si acaso
                'sqlite': {'database_name': 'dummy.db', 'table_name': 'dummy_table'}
            },
             'logging': {'level': 'DEBUG'} # Para ver logs si algo falla
        }

    # Necesitamos parchear config_loader Y el PROJECT_ROOT que usa para construir la ruta absoluta.
    monkeypatch.setattr(config_loader, 'get_config', mock_get_config_for_csv)
    # Hacemos que PROJECT_ROOT apunte a un directorio base temporal para que la export_directory relativa funcione.
    # El export_directory en el mock es relativo a este project_root parcheado.
    # tmp_path es la mejor opción como raíz simulada aquí.
    monkeypatch.setattr(config_loader, 'PROJECT_ROOT', tmp_path) # Usar tmp_path como raíz simulada

    # Datos a exportar (usamos una copia sin los None ID, y sin duplicados/inválidos)
    jobs_to_export = [j for j in sample_job_data if j['url'] and j['url'] != sample_job_data[0]['url'] or j == sample_job_data[0]]
    # Le añadimos un ID simulado, ya que CSV_HEADERS lo espera
    for i, job in enumerate(jobs_to_export): job['id'] = i + 1
    # Y fecha inserción simulada
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    for job in jobs_to_export: job['fecha_insercion'] = now_str


    # 2. Llamar a la función de exportación
    file_exporter.export_to_csv(jobs_to_export)

    # 3. Verificar que el archivo se creó
    # Necesitamos encontrar el archivo exacto. Podríamos buscar por patrón.
    created_files = list(test_output_dir.glob("*.csv"))
    print(f"Archivos creados en {test_output_dir}: {created_files}")
    assert len(created_files) == 1, "No se creó exactamente un archivo CSV."
    csv_file_path = created_files[0]
    assert expected_filename_part in csv_file_path.name, f"El nombre del archivo CSV '{csv_file_path.name}' no contiene la fecha esperada."

    # 4. Verificar contenido del CSV
    try:
        with open(csv_file_path, mode='r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            # Leer cabecera
            header = next(reader)
            # Comprobar si las cabeceras coinciden con las definidas en file_exporter (si las exporta)
            # Asumiendo que file_exporter.CSV_HEADERS existe y es la referencia
            if hasattr(file_exporter, 'CSV_HEADERS'):
                 assert header == file_exporter.CSV_HEADERS, "Las cabeceras del CSV no coinciden."
            else:
                 # Si no, al menos comprobar que hay una cabecera con X columnas
                 assert len(header) > 5, "La cabecera del CSV parece incorrecta."

            # Leer datos
            data_rows = list(reader)
            assert len(data_rows) == len(jobs_to_export), "El número de filas de datos en CSV no coincide."
            # Comprobar algún dato específico de la primera fila de datos (índice 0)
            # El orden debe coincidir con CSV_HEADERS si lo estamos usando para verificar
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