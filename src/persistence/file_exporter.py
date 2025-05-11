# -*- coding: utf-8 -*-
# /src/persistence/file_exporter.py

"""
Exportador de Datos a Archivos (por ahora, solo CSV).
(Versión con 'salario' añadido a las cabeceras)
"""

import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Importamos config_loader de forma segura
try:
    from src.utils import config_loader
except ImportError:
    logging.basicConfig(level=logging.WARNING)
    logging.warning("No se pudo importar config_loader en file_exporter.")
    config_loader = None

logger = logging.getLogger(__name__)

# --- ¡CORRECCIÓN AQUÍ! ---
# Añadimos 'salario' a la lista de cabeceras esperadas.
CSV_HEADERS = [
    'titulo',
    'empresa',
    'ubicacion',
    'salario',          # <-- AÑADIDO
    'fecha_publicacion',
    'url',
    'fuente',
    'fecha_insercion',
    'descripcion',
]


def export_to_csv(job_offers: List[Dict[str, Any]]):
    """ Exporta una lista de ofertas de empleo a un archivo CSV. """
    logger.info("Iniciando proceso de exportación a CSV...")
    project_root_dir = Path('.')
    csv_config = {}
    export_enabled = False
    output_dir_name = 'data/historico_default_csv' # Default distinto por si acaso
    filename_format = 'ofertas_{date}_default.csv' # Default

    try:
        # Cargar configuración de forma segura
        if config_loader:
             config = config_loader.get_config()
             if config:
                csv_config = config.get('data_storage', {}).get('csv', {})
                export_enabled = csv_config.get('export_enabled', False)
                output_dir_name = csv_config.get('export_directory', output_dir_name)
                filename_format = csv_config.get('filename_format', filename_format)
                if hasattr(config_loader, 'PROJECT_ROOT'):
                     project_root_dir = config_loader.PROJECT_ROOT
             else: logger.warning("Configuración global no cargada.")
        else: logger.warning("config_loader no disponible.")


        if not export_enabled:
            logger.info("Exportación a CSV deshabilitada. Omitiendo.")
            return

        if not job_offers:
            logger.info("No hay ofertas para exportar a CSV.")
            return

        # Generar nombre de archivo y rutas
        today_str = datetime.now().strftime('%Y-%m-%d')
        csv_filename = filename_format.replace('{date}', today_str)
        output_dir = project_root_dir / output_dir_name
        output_file_path = output_dir / csv_filename

        # Asegurar directorio
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directorio de exportación CSV: {output_dir}")

        logger.info(f"Exportando {len(job_offers)} ofertas a: {output_file_path}")

        # Escribir CSV
        try:
            with open(output_file_path, mode='w', encoding='utf-8', newline='') as csvfile:
                # Usamos extrasaction='ignore' por si los diccionarios tuvieran claves extras.
                writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(job_offers)
            logger.info(f"¡Exportación a CSV completada exitosamente! {len(job_offers)} filas escritas.")
        except (IOError, csv.Error, ValueError) as e: # Capturar ValueError también
             # El error específico que vimos era ValueError, lo capturamos aquí.
             logger.error(f"Error al escribir el archivo CSV en {output_file_path}: {e}", exc_info=True)
             # Logueamos también las cabeceras esperadas y las claves de la primera fila para depurar
             if job_offers:
                 logger.error(f"Cabeceras CSV esperadas: {CSV_HEADERS}")
                 logger.error(f"Claves en la primera oferta: {list(job_offers[0].keys())}")

    except Exception as e:
        logger.exception(f"Error inesperado durante la exportación a CSV: {e}")