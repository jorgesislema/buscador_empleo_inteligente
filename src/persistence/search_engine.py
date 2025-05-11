# -*- coding: utf-8 -*-
# /src/persistence/search_engine.py

"""
Motor de búsqueda de texto completo para las ofertas de trabajo.

Este módulo implementa búsqueda de texto completo usando la extensión FTS5 de SQLite,
permitiendo búsquedas más eficientes y relevantes en las descripciones de las ofertas.
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys

# Configuración de rutas para importaciones
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils import config_loader

logger = logging.getLogger(__name__)

class JobSearchEngine:
    """
    Motor de búsqueda de texto completo para ofertas de trabajo.
    
    Utiliza SQLite FTS5 (Full Text Search) para búsquedas eficientes
    y relevantes dentro del contenido de las ofertas de trabajo.
    """
    
    def __init__(self):
        """Inicializa el motor de búsqueda."""
        logger.info("Inicializando JobSearchEngine...")
        try:
            # Cargamos la configuración y obtenemos la ruta a la BD
            config = config_loader.get_config()
            db_config = config.get('data_storage', {}).get('sqlite', {})
            db_filename = db_config.get('database_name', 'jobs.db')
            self.table_name = db_config.get('table_name', 'jobs')
            
            # Ruta a la BD
            self.db_path = config_loader.PROJECT_ROOT / "data" / db_filename
            logger.info(f"Utilizando base de datos: {self.db_path}")
            
            # Crear tabla virtual FTS5 si no existe
            self._setup_fts()
            
        except Exception as e:
            logger.exception(f"Error al inicializar JobSearchEngine: {e}")
            raise e
    
    def _setup_fts(self):
        """Configura la tabla virtual FTS5 si no existe."""
        logger.info("Configurando tabla virtual FTS5...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Verificar si la tabla FTS ya existe
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs_fts'")
                if cursor.fetchone() is None:
                    logger.info("Creando tabla virtual FTS5...")
                    
                    # Crear tabla virtual FTS5
                    # FTS5 proporciona búsqueda de texto completo optimizada
                    cursor.execute('''
                    CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
                        id, titulo, empresa, ubicacion, descripcion, 
                        fecha_publicacion, url, fuente, fecha_insercion,
                        content=jobs, content_rowid=id
                    )
                    ''')
                    
                    # Poblar la tabla FTS con datos existentes
                    cursor.execute(f'''
                    INSERT INTO jobs_fts(id, titulo, empresa, ubicacion, descripcion, 
                                      fecha_publicacion, url, fuente, fecha_insercion)
                    SELECT id, titulo, empresa, ubicacion, descripcion, 
                           fecha_publicacion, url, fuente, fecha_insercion 
                    FROM {self.table_name}
                    ''')
                    
                    # Crear triggers para mantener sincronizada la tabla FTS
                    # Trigger para nuevas inserciones
                    cursor.execute(f'''
                    CREATE TRIGGER jobs_ai AFTER INSERT ON {self.table_name} BEGIN
                        INSERT INTO jobs_fts(id, titulo, empresa, ubicacion, descripcion, 
                                        fecha_publicacion, url, fuente, fecha_insercion)
                        VALUES (new.id, new.titulo, new.empresa, new.ubicacion, new.descripcion, 
                                new.fecha_publicacion, new.url, new.fuente, new.fecha_insercion);
                    END;
                    ''')
                    
                    # Trigger para eliminaciones
                    cursor.execute(f'''
                    CREATE TRIGGER jobs_ad AFTER DELETE ON {self.table_name} BEGIN
                        DELETE FROM jobs_fts WHERE id = old.id;
                    END;
                    ''')
                    
                    # Trigger para actualizaciones
                    cursor.execute(f'''
                    CREATE TRIGGER jobs_au AFTER UPDATE ON {self.table_name} BEGIN
                        DELETE FROM jobs_fts WHERE id = old.id;
                        INSERT INTO jobs_fts(id, titulo, empresa, ubicacion, descripcion, 
                                        fecha_publicacion, url, fuente, fecha_insercion)
                        VALUES (new.id, new.titulo, new.empresa, new.ubicacion, new.descripcion, 
                                new.fecha_publicacion, new.url, new.fuente, new.fecha_insercion);
                    END;
                    ''')
                    
                    logger.info("Tabla virtual FTS5 y triggers creados exitosamente")
                else:
                    logger.info("La tabla virtual FTS5 ya existe")
                
        except sqlite3.Error as e:
            logger.exception(f"Error al configurar FTS5: {e}")
            raise e
    
    def search(self, query: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Realiza una búsqueda de texto completo.
        
        Args:
            query: Texto a buscar
            limit: Número máximo de resultados
            offset: Número de resultados a saltar (para paginación)
            
        Returns:
            Lista de ofertas que coinciden con la búsqueda
        """
        logger.info(f"Realizando búsqueda FTS para: '{query}'")
        
        if not query or query.strip() == "":
            logger.warning("Consulta de búsqueda vacía")
            return []
        
        try:
            # Sanitizar y preparar consulta
            # Convertimos espacios en OR para búsqueda más flexible
            sanitized_query = ' OR '.join(query.strip().split())
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = self._dict_factory
                cursor = conn.cursor()
                
                # Búsqueda FTS con ranking
                cursor.execute('''
                SELECT * FROM jobs_fts 
                WHERE jobs_fts MATCH ? 
                ORDER BY rank 
                LIMIT ? OFFSET ?
                ''', (sanitized_query, limit, offset))
                
                results = cursor.fetchall()
                logger.info(f"Búsqueda completada, {len(results)} resultados")
                return results
                
        except sqlite3.Error as e:
            logger.exception(f"Error durante la búsqueda FTS: {e}")
            return []
    
    def _dict_factory(self, cursor, row):
        """Convierte filas de SQLite a diccionarios."""
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d
    
    def get_total_results(self, query: str) -> int:
        """
        Obtiene el número total de resultados para una búsqueda.
        
        Args:
            query: Texto a buscar
            
        Returns:
            Número total de resultados
        """
        if not query or query.strip() == "":
            return 0
        
        try:
            sanitized_query = ' OR '.join(query.strip().split())
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                SELECT COUNT(*) FROM jobs_fts 
                WHERE jobs_fts MATCH ?
                ''', (sanitized_query,))
                
                return cursor.fetchone()[0]
                
        except sqlite3.Error as e:
            logger.exception(f"Error al obtener total de resultados: {e}")
            return 0

# Ejemplo de uso (si se ejecuta directamente)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, 
                        format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
    
    print("--- Probando JobSearchEngine ---")
    try:
        search_engine = JobSearchEngine()
        
        # Realizar algunas búsquedas de prueba
        test_queries = [
            "python django",
            "remote developer",
            "data scientist",
            "machine learning"
        ]
        
        for query in test_queries:
            print(f"\nBúsqueda para: '{query}'")
            results = search_engine.search(query, limit=5)
            total = search_engine.get_total_results(query)
            
            print(f"Total de resultados: {total}")
            print(f"Mostrando primeros {len(results)} resultados:")
            
            for i, job in enumerate(results, 1):
                print(f"{i}. {job.get('titulo', 'Sin título')} - {job.get('empresa', 'Sin empresa')}")
                print(f"   Ubicación: {job.get('ubicacion', 'No especificada')}")
                print(f"   URL: {job.get('url', 'No disponible')}")
                print()
                
    except Exception as e:
        print(f"Error: {e}")