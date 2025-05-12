# -*- coding: utf-8 -*-
# /src/persistence/database_manager.py

"""
Gestor de la Base de Datos SQLite.

Este módulo es nuestro único punto de contacto con la base de datos.
Se encarga de todo: conectar, asegurar que la tabla exista,
e insertar las ofertas de empleo que vayamos encontrando.
Usamos SQLite porque es sencillo y perfecto para este tipo de proyecto.

La idea es crear una instancia de DatabaseManager al principio y luego
usar su método 'insert_job_offers' para guardar los datos.
"""

import sqlite3
import logging
from typing import List, Dict, Any
from datetime import datetime
from src.utils import config_loader

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        logger.info("Inicializando el DatabaseManager...")
        try:
            config = config_loader.get_config()
            db_config = config.get('data_storage', {}).get('sqlite', {})
            db_filename = db_config.get('database_name', 'jobs_default.db')
            self.table_name = db_config.get('table_name', 'ofertas_empleo_default')
            self.db_path = config_loader.PROJECT_ROOT / "data" / db_filename

            logger.info(f"Ruta de la base de datos configurada: {self.db_path}")
            logger.info(f"Tabla a usar: {self.table_name}")

            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._initialize_database()

        except Exception as e:
            logger.exception("¡Error crítico durante la inicialización del DatabaseManager! No se podrá usar la BD.")
            raise e

    def _initialize_database(self):
        logger.debug(f"Asegurando que la tabla '{self.table_name}' exista en {self.db_path}...")
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            empresa TEXT,
            ubicacion TEXT,
            descripcion TEXT,
            fecha_publicacion TEXT,
            url TEXT UNIQUE,
            fuente TEXT,
            fecha_insercion DATETIME
        );
        """
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                logger.debug(f"Ejecutando: {create_table_sql}")
                cursor.execute(create_table_sql)
            logger.info(f"Tabla '{self.table_name}' asegurada/creada exitosamente.")
        except sqlite3.Error as e:
            logger.exception(f"Error al inicializar la base de datos o crear la tabla '{self.table_name}': {e}")
            raise e

    def insert_job_offers(self, job_offers: List[Dict[str, Any]]):
        if not job_offers:
            logger.info("No hay ofertas de empleo para insertar.")
            return

        logger.info(f"Intentando insertar {len(job_offers)} ofertas de empleo en la tabla '{self.table_name}'...")

        sql = f"""
        INSERT OR IGNORE INTO {self.table_name} (
            titulo, empresa, ubicacion, descripcion, fecha_publicacion,
            url, fuente, fecha_insercion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data_to_insert = []
        for job in job_offers:
            data_tuple = (
                job.get('titulo'),
                job.get('empresa'),
                job.get('ubicacion'),
                job.get('descripcion'),
                job.get('fecha_publicacion'),
                job.get('url'),
                job.get('fuente'),
                now_str
            )
            if data_tuple[5]:
                data_to_insert.append(data_tuple)
            else:
                logger.warning(f"Oferta omitida por no tener URL: {job.get('titulo', 'Sin título')}")

        if not data_to_insert:
            logger.warning("Ninguna oferta válida para insertar después de filtrar las que no tienen URL.")
            return

        try:
            inserted_count = 0
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.executemany(sql, data_to_insert)
                inserted_count = conn.total_changes

            logger.info(f"Se intentó insertar {len(data_to_insert)} ofertas.")
            logger.info(f"Inserción de {len(data_to_insert)} ofertas completada (duplicados basados en URL fueron ignorados).")

        except sqlite3.Error as e:
            logger.exception(f"Error al insertar ofertas de empleo en la base de datos: {e}")

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')

    print("--- Probando el DatabaseManager ---")
    try:
        db_manager = DatabaseManager()
        print(f"DatabaseManager inicializado. Usando BD en: {db_manager.db_path}")

        ofertas_prueba = [
            {
                'titulo': 'Data Scientist Jr.',
                'empresa': 'Startup Innovadora',
                'ubicacion': 'Quito',
                'descripcion': 'Buscamos talento para análisis de datos...',
                'fecha_publicacion': '2025-05-01',
                'url': 'https://ejemplo.com/oferta/123',
                'fuente': 'Test'
            },
            {
                'titulo': 'Data Engineer',
                'empresa': 'Gran Empresa Tech',
                'ubicacion': 'Remote Ecuador',
                'descripcion': 'Experiencia en ETL y Cloud necesaria...',
                'fecha_publicacion': '2025-04-30',
                'url': 'https://ejemplo.com/oferta/456',
                'fuente': 'Test'
            },
            {
                'titulo': 'Data Scientist Jr. (Duplicado)',
                'empresa': 'Startup Innovadora',
                'ubicacion': 'Quito',
                'descripcion': 'Buscamos talento...',
                'fecha_publicacion': '2025-05-01',
                'url': 'https://ejemplo.com/oferta/123',
                'fuente': 'Test Duplicado'
            },
            {
                'titulo': 'Analista BI Sin URL',
                'empresa': 'Consultora X',
                'ubicacion': 'Remoto',
                'descripcion': '...',
                'fecha_publicacion': '2025-05-01',
                'url': None,
                'fuente': 'Test Sin URL'
            }
        ]

        print(f"\nIntentando insertar {len(ofertas_prueba)} ofertas de prueba...")
        db_manager.insert_job_offers(ofertas_prueba)
        print("\nInserción finalizada (revisar logs para detalles).")
        print("-> La oferta duplicada y la oferta sin URL deberían haber sido ignoradas/omitidas.")

    except Exception as e:
        print(f"\n--- Ocurrió un error durante la prueba del DatabaseManager ---")
        logger.exception("Error en prueba de DatabaseManager:")
