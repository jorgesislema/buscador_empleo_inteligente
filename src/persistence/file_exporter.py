# -*- coding: utf-8 -*-
# /src/persistence/file_exporter.py

"""
Exportador de Datos a Archivos (por ahora, solo CSV).

Este módulo se encarga de tomar una lista de ofertas de empleo
(probablemente ya filtradas y procesadas) y guardarlas en un archivo CSV.

Le preguntaremos a la configuración si esta función está habilitada y dónde
guardar los archivos antes de hacer nada. ¡Flexibilidad ante todo!
"""

import csv              # La librería estándar de Python para trabajar con archivos CSV.
import logging          # Para registrar mensajes sobre la exportación.
from pathlib import Path   # Para manejar rutas de archivos de forma moderna.
from typing import List, Dict, Any # Para los type hints que nos gustan.
from datetime import datetime   # Para generar la fecha para el nombre del archivo.

# Importamos nuestro confiable cargador de configuración.
from src.utils import config_loader

# Obtenemos un logger para este módulo.
logger = logging.getLogger(__name__)

# --- Constantes ---
# Definimos aquí las cabeceras que queremos en nuestro archivo CSV y su orden.
# Es mejor tenerlas fijas que depender de las claves del primer diccionario de la lista.
# Podemos basarnos en las columnas de la base de datos para consistencia.
CSV_HEADERS = [
    'id', # Aunque venga de la BD, puede ser útil tenerlo en el CSV. O lo quitamos si no se inserta aún.
    'titulo',
    'empresa',
    'ubicacion',
    'descripcion', # Ojo, la descripción puede tener comas o saltos de línea, csv manejará esto.
    'fecha_publicacion',
    'url',
    'fuente',
    'fecha_insercion' # Cuándo se añadió a nuestra BD/proceso.
]


def export_to_csv(job_offers: List[Dict[str, Any]]):
    """
    Exporta una lista de ofertas de empleo a un archivo CSV.

    Lee la configuración para saber si debe ejecutarse, dónde guardar el archivo
    y cómo nombrarlo (usando la fecha actual).

    Args:
        job_offers (List[Dict[str, Any]]): La lista de diccionarios de ofertas a exportar.
                                             Se espera que las claves coincidan con CSV_HEADERS.
    """
    logger.info("Iniciando proceso de exportación a CSV...")

    try:
        # 1. Chequeamos la configuración primero.
        config = config_loader.get_config()
        csv_config = config.get('data_storage', {}).get('csv', {})

        export_enabled = csv_config.get('export_enabled', False) # ¿Está habilitado? False por defecto.
        if not export_enabled:
            logger.info("La exportación a CSV está deshabilitada en la configuración. Omitiendo.")
            return # No hacemos nada más si está deshabilitado. ¡Fácil!

        # Si llegamos aquí, ¡está habilitado! Sacamos el resto de la config.
        output_dir_name = csv_config.get('export_directory', 'data/csv_exports_default') # Carpeta destino.
        filename_format = csv_config.get('filename_format', 'jobs_{date}_default.csv') # Formato del nombre.

        # 2. Verificamos si hay datos para exportar.
        if not job_offers:
            logger.info("No hay ofertas de empleo para exportar a CSV en esta ejecución.")
            # Podríamos decidir crear un archivo CSV vacío o simplemente no hacer nada.
            # Por ahora, no hacemos nada si la lista está vacía.
            return

        # 3. Generamos el nombre del archivo final.
        today_str = datetime.now().strftime('%Y-%m-%d') # Fecha de hoy como YYYY-MM-DD.
        # Reemplazamos la parte '{date}' en el formato con la fecha de hoy.
        csv_filename = filename_format.replace('{date}', today_str)

        # Construimos la ruta completa al directorio de salida y al archivo.
        output_dir = config_loader.PROJECT_ROOT / output_dir_name
        output_file_path = output_dir / csv_filename

        # 4. Nos aseguramos de que el directorio de salida exista.
        logger.debug(f"Asegurando que el directorio de exportación exista: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True) # ¡Viva pathlib!

        # 5. ¡A escribir el archivo CSV!
        logger.info(f"Exportando {len(job_offers)} ofertas a: {output_file_path}")

        # Abrimos el archivo en modo escritura ('w').
        # encoding='utf-8' es importante para caracteres especiales (acentos, etc.).
        # newline='' es CRUCIAL para evitar filas en blanco extra en Windows.
        with open(output_file_path, mode='w', encoding='utf-8', newline='') as csvfile:
            # Creamos un 'escritor' de diccionarios. Le pasamos el archivo y los nombres de campo (cabeceras).
            # DictWriter es genial porque podemos pasarle directamente nuestros diccionarios de ofertas.
            writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)

            # Escribimos la primera fila con las cabeceras.
            writer.writeheader()

            # Ahora, recorremos nuestra lista de ofertas y escribimos cada una como una fila.
            # DictWriter se encarga de poner cada valor en la columna correcta según la cabecera.
            # Si a una oferta le falta una clave que está en CSV_HEADERS, escribirá una celda vacía.
            writer.writerows(job_offers) # ¡Más eficiente que writerow en un bucle!

        logger.info(f"¡Exportación a CSV completada exitosamente! {len(job_offers)} filas escritas.")

    except KeyError as e:
        # Esto podría pasar si la estructura de 'config' no es la esperada.
        logger.error(f"Error de configuración al intentar exportar a CSV. Falta la clave: {e}", exc_info=True)
    except IOError as e:
        # Errores al escribir en el archivo (disco lleno, permisos, etc.)
        logger.error(f"Error de E/S al escribir el archivo CSV en {output_file_path}: {e}", exc_info=True)
    except csv.Error as e:
        # Errores específicos de la librería CSV.
        logger.error(f"Error de la librería CSV durante la exportación: {e}", exc_info=True)
    except Exception as e:
        # ¡El cajón de sastre para cualquier otro problema inesperado!
        logger.exception(f"Error inesperado durante la exportación a CSV: {e}")


# --- Ejemplo de Uso (si ejecutamos este script directamente) ---
if __name__ == '__main__':
    # Configuración rápida de logging y config para la prueba.
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
    # Para que esta prueba funcione, necesitaríamos tener un settings.yaml y .env válidos
    # o simular la configuración aquí. Vamos a simularla para que sea autocontenida.

    # Simulamos que cargamos esta config:
    class MockConfigLoader:
        PROJECT_ROOT = Path(__file__).parent.parent.parent
        def get_config(self):
            return {
                'data_storage': {
                    'csv': {
                        'export_enabled': True,
                        'export_directory': 'data/historico_test', # Usamos un dir de prueba
                        'filename_format': 'ofertas_test_{date}.csv'
                    }
                },
                'logging': {'level': 'DEBUG', 'log_file': 'test.log'} # Dummy logging config
            }
    # Sobreescribimos la función real con nuestro simulador SOLO para esta prueba.
    config_loader.get_config = MockConfigLoader().get_config
    config_loader.PROJECT_ROOT = MockConfigLoader.PROJECT_ROOT


    print("--- Probando el FileExporter (export_to_csv) ---")

    # Preparamos datos de ejemplo (similares a los de database_manager)
    ofertas_para_csv = [
        {
            'id': 1, 'titulo': 'Data Scientist', 'empresa': 'TestCo', 'ubicacion': 'Quito',
            'descripcion': 'Descripción con, comas y\nsaltos de línea.', 'fecha_publicacion': '2025-05-01',
            'url': 'http://test.com/1', 'fuente': 'CSV Test', 'fecha_insercion': '2025-05-10 10:00:00',
            'campo_extra': 'esto se ignorará' # DictWriter ignora claves no en fieldnames
        },
        {
            'id': 2, 'titulo': 'Data Engineer', 'empresa': 'AnotherTest', 'ubicacion': 'Remote Ecuador',
            'descripcion': 'ETL, Cloud, etc.', 'fecha_publicacion': '2025-05-02',
            'url': 'http://test.com/2', 'fuente': 'CSV Test', 'fecha_insercion': '2025-05-10 10:01:00'
            # Falta 'id' en este dict? DictWriter pondrá celda vacía si 'id' está en headers.
            # Lo hemos puesto en CSV_HEADERS, así que lo añadimos aquí también.
        },
        { # Sin algunas claves
            'id': 3, 'titulo': 'BI Analyst', 'empresa': 'BI Corp',
             # falta ubicacion, descripcion
            'fecha_publicacion': '2025-05-03',
            'url': 'http://test.com/3', 'fuente': 'CSV Test', 'fecha_insercion': '2025-05-10 10:02:00'
        }
    ]

    # Llamamos a nuestra función para exportar.
    export_to_csv(ofertas_para_csv)

    print(f"\nRevisa si se creó la carpeta '{MockConfigLoader.PROJECT_ROOT / 'data/historico_test'}'")
    print(f"y dentro el archivo 'ofertas_test_{datetime.now().strftime('%Y-%m-%d')}.csv'")
    print("Abre el archivo CSV para verificar el contenido y las cabeceras.")

    # Prueba con exportación deshabilitada (simulando cambio en config)
    print("\n--- Probando con exportación deshabilitada ---")
    class MockConfigLoaderDisabled(MockConfigLoader):
         def get_config(self):
             config = super().get_config()
             config['data_storage']['csv']['export_enabled'] = False
             return config
    config_loader.get_config = MockConfigLoaderDisabled().get_config
    export_to_csv(ofertas_para_csv) # No debería hacer nada más que loguear un mensaje INFO.