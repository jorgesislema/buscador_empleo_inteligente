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

import sqlite3        # ¡La librería incorporada en Python para SQLite!
import logging        # Para registrar qué estamos haciendo con la BD.
from pathlib import Path # Para construir la ruta a la BD.
from typing import List, Dict, Any # Para type hints, ¡buenas prácticas!
from datetime import datetime # Para registrar cuándo insertamos los datos.

# Importamos nuestro cargador de configuración para saber cómo se llama la BD y la tabla.
from src.utils import config_loader

# Obtenemos un logger para este módulo.
logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Gestiona la conexión y las operaciones con la base de datos SQLite.
    """
    def __init__(self):
        """
        Inicializa el gestor de la base de datos.

        Carga la configuración, construye la ruta a la BD y se asegura
        de que la tabla necesaria exista.
        """
        logger.info("Inicializando el DatabaseManager...")
        try:
            # Cargamos la configuración general.
            config = config_loader.get_config()
            db_config = config.get('data_storage', {}).get('sqlite', {}) # Sacamos la config de SQLite.

            # Nombre del archivo de la BD y nombre de la tabla. Usamos defaults por si acaso.
            db_filename = db_config.get('database_name', 'jobs_default.db')
            self.table_name = db_config.get('table_name', 'ofertas_empleo_default')

            # Construimos la ruta completa al archivo de la BD.
            # Estará dentro de la carpeta 'data/' en la raíz del proyecto.
            self.db_path = config_loader.PROJECT_ROOT / "data" / db_filename
            logger.info(f"Ruta de la base de datos configurada: {self.db_path}")
            logger.info(f"Tabla a usar: {self.table_name}")

            # ¡Importante! Nos aseguramos de que la carpeta 'data' exista.
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Y ahora, nos aseguramos de que la tabla esté creada.
            self._initialize_database()

        except Exception as e:
            logger.exception("¡Error crítico durante la inicialización del DatabaseManager! No se podrá usar la BD.")
            # Relanzamos para que el programa principal sepa que algo fue muy mal.
            raise e

    def _initialize_database(self):
        """
        Asegura que la tabla necesaria exista en la base de datos.

        Se conecta a la BD y ejecuta un 'CREATE TABLE IF NOT EXISTS'.
        Esto es seguro de llamar múltiples veces; solo crea la tabla la primera vez.
        """
        logger.debug(f"Asegurando que la tabla '{self.table_name}' exista en {self.db_path}...")

        # Definimos la estructura de nuestra tabla. ¡Aquí decidimos qué guardar!
        # Usamos TEXT para la mayoría de campos. INTEGER PRIMARY KEY AUTOINCREMENT para un ID único.
        # ¡Muy importante! Añadimos UNIQUE(url) para evitar duplicados basados en la URL.
        # Añadimos 'fecha_insercion' para saber cuándo guardamos cada oferta.
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT,
            empresa TEXT,
            ubicacion TEXT,
            descripcion TEXT,
            fecha_publicacion TEXT, -- Guardamos como texto, la normalización se haría antes o al leer.
            url TEXT UNIQUE,        -- La URL será nuestra clave para evitar duplicados.
            fuente TEXT,          -- De dónde vino la oferta (ej: 'Adzuna', 'Computrabajo').
            fecha_insercion DATETIME -- Cuándo la insertamos en nuestra BD.
            -- Podríamos añadir más campos si los necesitamos, como 'salario', 'tipo_contrato', etc.
        );
        """
        try:
            # Nos conectamos a la BD. El archivo se crea si no existe.
            # Usamos 'with' para que la conexión se cierre y haga commit automáticamente. ¡Muy cómodo!
            with sqlite3.connect(self.db_path, timeout=10) as conn: # Timeout por si la BD está ocupada.
                cursor = conn.cursor() # Necesitamos un cursor para ejecutar SQL.
                logger.debug(f"Ejecutando: {create_table_sql}")
                cursor.execute(create_table_sql) # ¡Creamos la tabla! (si no existe)
                # No necesitamos commit explícito porque 'with' se encarga al salir del bloque sin errores.
            logger.info(f"Tabla '{self.table_name}' asegurada/creada exitosamente.")
        except sqlite3.Error as e:
            # ¡Ojo! Si hay un error con la BD (disco lleno, permisos, SQL inválido...)
            logger.exception(f"Error al inicializar la base de datos o crear la tabla '{self.table_name}': {e}")
            # Relanzamos la excepción porque si no podemos crear/acceder a la tabla, poco podemos hacer.
            raise e

    def insert_job_offers(self, job_offers: List[Dict[str, Any]]):
        """
        Inserta una lista de ofertas de empleo en la base de datos.

        Usa 'INSERT OR IGNORE', por lo que las ofertas cuya URL ya exista
        en la base de datos serán ignoradas silenciosamente (no insertadas).

        Args:
            job_offers (List[Dict[str, Any]]): Una lista de diccionarios, donde cada
                                             diccionario representa una oferta de empleo
                                             y sus claves coinciden (idealmente) con los
                                             nombres de las columnas de la tabla.
        """
        if not job_offers:
            logger.info("No hay ofertas de empleo para insertar.")
            return

        logger.info(f"Intentando insertar {len(job_offers)} ofertas de empleo en la tabla '{self.table_name}'...")

        # Preparamos la sentencia SQL.
        # Usamos 'INSERT OR IGNORE' para que si una URL ya existe (por la restricción UNIQUE),
        # simplemente se ignore esa fila y no dé error, continuando con las demás.
        # Definimos las columnas explícitamente para asegurarnos del orden.
        # Usamos placeholders '?' para los valores. ¡Más seguro contra inyección SQL!
        sql = f"""
        INSERT OR IGNORE INTO {self.table_name} (
            titulo, empresa, ubicacion, descripcion, fecha_publicacion,
            url, fuente, fecha_insercion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """

        # Preparamos los datos para 'executemany'.
        # Necesitamos una lista de tuplas, donde cada tupla contenga los valores
        # en el MISMO ORDEN que las columnas en el INSERT.
        # Usamos .get(key, None) para evitar errores si alguna clave falta en algún diccionario de oferta.
        # Añadimos la fecha y hora actual para 'fecha_insercion'.
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S') # Fecha y hora actual como texto.
        data_to_insert = []
        for job in job_offers:
            # Extraemos los datos, poniendo None si alguna clave no está. ¡Hay que ser flexibles!
            data_tuple = (
                job.get('titulo'),
                job.get('empresa'),
                job.get('ubicacion'),
                job.get('descripcion'),
                job.get('fecha_publicacion'), # Asumimos que ya viene como texto.
                job.get('url'),
                job.get('fuente'),
                now_str # Usamos la misma fecha/hora de inserción para todo el lote.
            )
            # ¡Validación básica! Necesitamos al menos una URL para que UNIQUE funcione.
            if data_tuple[5]: # Índice 5 corresponde a la URL.
                data_to_insert.append(data_tuple)
            else:
                logger.warning(f"Oferta omitida por no tener URL: {job.get('titulo', 'Sin título')}")


        if not data_to_insert:
            logger.warning("Ninguna oferta válida para insertar después de filtrar las que no tienen URL.")
            return

        inserted_count = 0 # Contador para saber cuántas realmente se insertaron.
        try:
            # Nos conectamos usando 'with' para manejo automático de transacciones.
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                # ¡Ejecutamos la inserción de múltiples filas! Es más eficiente que hacer un INSERT por cada una.
                cursor.executemany(sql, data_to_insert)
                # conn.commit() # No es necesario explícitamente dentro de 'with' si no hay error.
                # rowcount podría no ser fiable con INSERT OR IGNORE en todas las versiones/casos.
                # Es más fiable ver los cambios totales si es necesario, pero saber cuántos se intentaron es útil.
                # inserted_count = cursor.rowcount # Podríamos intentar usarlo, pero con cautela.
                inserted_count = conn.total_changes # Mejor forma de saber cuántas filas cambiaron en la sesión actual

            # Usamos conn.total_changes que es más fiable después de cerrar la conexión implícita.
            # Necesitamos una forma de obtener los cambios hechos por ESTA operación.
            # Vamos a registrar cuántos intentamos y cuántos *pudieron* insertarse (aproximado).
            # Para saberlo exacto, necesitaríamos consultar antes y después, o no usar IGNORE.
            # Por ahora, informaremos el intento y confiaremos en "INSERT OR IGNORE".
            # La variable inserted_count arriba es más un placeholder conceptual aquí.
            # Podríamos hacer un SELECT COUNT(*) antes y después para saber el número exacto, pero complica.

            # Vamos a reabrir y contar para tener una idea, aunque no sea lo más eficiente.
            # O mejor, confiamos en el logger que dice cuántas se intentaron.
            logger.info(f"Se intentó insertar {len(data_to_insert)} ofertas.")
            # Para saber cuántas fueron NUEVAS, podríamos consultar la diferencia.
            # Otra opción es que el método devuelva las URLs que SÍ insertó.

            # Simplifiquemos: Logueamos el intento y mencionamos que duplicados (por URL) se ignoran.
            logger.info(f"Inserción de {len(data_to_insert)} ofertas completada (duplicados basados en URL fueron ignorados).")


        except sqlite3.Error as e:
            # Si algo falla durante la inserción masiva...
            logger.exception(f"Error al insertar ofertas de empleo en la base de datos: {e}")
            # Nota: 'with' se encarga del rollback en caso de error.

    # --- Podríamos añadir más métodos aquí ---
    # Por ejemplo, para leer datos, actualizar, borrar, etc.
    # def get_all_jobs(self) -> List[Dict[str, Any]]: ...
    # def get_job_by_url(self, url: str) -> Dict[str, Any] | None: ...
    # def delete_old_jobs(self, days_old: int): ...


# --- Ejemplo de Uso (si ejecutamos este script directamente) ---
if __name__ == '__main__':
    # Configuración rápida de logging para la prueba.
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')

    print("--- Probando el DatabaseManager ---")
    try:
        # 1. Creamos una instancia. Esto debería crear el archivo .db y la tabla si no existen.
        db_manager = DatabaseManager()
        print(f"DatabaseManager inicializado. Usando BD en: {db_manager.db_path}")

        # 2. Preparamos algunos datos de ejemplo.
        ofertas_prueba = [
            {
                'titulo': 'Data Scientist Jr.',
                'empresa': 'Startup Innovadora',
                'ubicacion': 'Quito',
                'descripcion': 'Buscamos talento para análisis de datos...',
                'fecha_publicacion': '2025-05-01',
                'url': 'https://ejemplo.com/oferta/123', # URL única
                'fuente': 'Test'
            },
            {
                'titulo': 'Data Engineer',
                'empresa': 'Gran Empresa Tech',
                'ubicacion': 'Remote Ecuador',
                'descripcion': 'Experiencia en ETL y Cloud necesaria...',
                'fecha_publicacion': '2025-04-30',
                'url': 'https://ejemplo.com/oferta/456', # URL única
                'fuente': 'Test'
            },
            { # Oferta duplicada (misma URL que la primera)
                'titulo': 'Data Scientist Jr. (Duplicado)',
                'empresa': 'Startup Innovadora',
                'ubicacion': 'Quito',
                'descripcion': 'Buscamos talento...',
                'fecha_publicacion': '2025-05-01',
                'url': 'https://ejemplo.com/oferta/123', # URL REPETIDA
                'fuente': 'Test Duplicado'
            },
             { # Oferta sin URL (Debería ser omitida)
                'titulo': 'Analista BI Sin URL',
                'empresa': 'Consultora X',
                'ubicacion': 'Remoto',
                'descripcion': '...',
                'fecha_publicacion': '2025-05-01',
                'url': None, # Sin URL
                'fuente': 'Test Sin URL'
            }
        ]

        # 3. Intentamos insertar las ofertas.
        print(f"\nIntentando insertar {len(ofertas_prueba)} ofertas de prueba...")
        db_manager.insert_job_offers(ofertas_prueba)
        print("\nInserción finalizada (revisar logs para detalles).")
        print("-> La oferta duplicada y la oferta sin URL deberían haber sido ignoradas/omitidas.")

        # 4. Podríamos añadir aquí código para leer de la BD y verificar,
        #    pero necesitaríamos implementar primero un método de lectura.
        #    print("\nContenido actual de la tabla (implementar lectura para ver)...")

    except Exception as e:
        print(f"\n--- Ocurrió un error durante la prueba del DatabaseManager ---")
        logger.exception("Error en prueba de DatabaseManager:")