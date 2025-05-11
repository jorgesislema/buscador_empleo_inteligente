# -*- coding: utf-8 -*-
# /scripts/inicializar_db.py

"""
Script para Inicializar la Base de Datos SQLite.

Este script simplemente crea una instancia del DatabaseManager.
Al hacerlo, el método __init__ del DatabaseManager se asegura
de que el archivo de base de datos exista y contenga la tabla
necesaria (definida con CREATE TABLE IF NOT EXISTS).

Útil para ejecutar una vez al configurar el proyecto por primera vez,
o para recrear la base de datos desde cero si borras el archivo .db.
"""

import logging
import sys
from pathlib import Path

# Añadimos la carpeta raíz del proyecto al PYTHONPATH para las importaciones
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Importamos lo necesario
try:
    from src.persistence.database_manager import DatabaseManager
    from src.utils import logging_config
    # No necesitamos cargar config explícitamente aquí, DatabaseManager lo hará.
except ImportError as e:
    print(f"Error: No se pudieron importar módulos necesarios: {e}")
    print("Asegúrate de ejecutar este script desde la carpeta raíz del proyecto.")
    print("Verifica que las rutas de los módulos 'src.persistence.database_manager' y 'src.utils.logging_config' sean correctas.")
    sys.exit(1)

# Configuración básica del logger para este script
logger = logging.getLogger("db_initializer")

def main():
    """Función principal para inicializar la base de datos."""
    # Primero configuramos el logging para ver qué pasa
    try:
        logging_config.setup_logging()
        logger.info("Sistema de logging configurado.")
    except Exception as e:
        # Si falla el logging, al menos imprimimos en consola.
        print(f"ADVERTENCIA: No se pudo configurar el logging avanzado: {e}. Se usarán mensajes básicos.")
        logging.basicConfig(level=logging.INFO)

    logger.info("--- Iniciando Inicialización de la Base de Datos ---")

    try:
        # La magia ocurre aquí: ¡Simplemente creamos una instancia!
        logger.info("Creando instancia de DatabaseManager para asegurar que la BD y la tabla existan...")
        db_manager = DatabaseManager()

        # Si llegamos aquí sin errores, la tabla debería existir.
        logger.info("¡Inicialización completada!")
        logger.info(f"Base de datos verificada/creada en: {db_manager.db_path}")
        logger.info(f"Tabla '{db_manager.table_name}' asegurada/creada.")
        print("\n-> ¡Base de datos lista para usar!")

    except Exception as e:
        # Capturamos cualquier error que pueda ocurrir durante la inicialización
        # (ej: error al leer config, problemas de permisos para crear el archivo/carpeta, SQL inválido)
        logger.exception("¡ERROR CRÍTICO durante la inicialización de la base de datos!")
        print(f"\nERROR: No se pudo inicializar la base de datos. Revisa los logs para más detalles. Error: {e}")

    logger.info("--- Fin de la Inicialización ---")

# Punto de entrada del script
if __name__ == "__main__":
    main()