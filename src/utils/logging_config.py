# -*- coding: utf-8 -*-
# /src/utils/logging_config.py

"""
Configuración del Logging para Nuestro Buscador de Empleo.

Aquí es donde montamos todo el sistema para que nuestra aplicación
pueda "hablar" y contarnos qué está haciendo, si hay errores, etc.
Leeremos la configuración desde nuestro 'settings.yaml' (usando el config_loader
que ya hicimos) y prepararemos los 'handlers' (dónde escribir los logs)
y los 'formatters' (cómo se verán esos mensajes).

La idea es llamar a la función setup_logging() al principio de nuestro
script principal (main.py) y ¡listo! La magia del logging estará configurada.
"""

import logging  # La librería estándar de Python para todo lo relacionado con logs.
import logging.config # Necesitamos específicamente dictConfig para configurar desde un diccionario. Es súper flexible.
import os       # Lo usaremos para asegurarnos de que exista la carpeta 'logs'.
from pathlib import Path # Para manejar las rutas de archivo de forma más elegante.
from typing import Optional, Dict, Any # Type hints

# Importamos nuestro propio módulo para cargar la configuración. ¡Trabajo en equipo!
# Usamos un try-except por si este módulo se importa antes o de forma aislada.
try:
    from src.utils import config_loader
except ImportError:
    # Si falla la importación, configuramos un logger básico y continuamos (con funcionalidad limitada)
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s - %(name)s - %(message)s')
    logging.warning("No se pudo importar config_loader. La configuración de logging usará valores por defecto.")
    config_loader = None # Marcamos que no está disponible
except Exception as e:
     logging.basicConfig(level=logging.ERROR, format='%(levelname)s - %(name)s - %(message)s')
     logging.error(f"Error inesperado al importar config_loader: {e}")
     config_loader = None


# Variable global para saber si ya hemos configurado el logging. ¡Evita trabajo doble!
_logging_configured = False

def setup_logging():
    """
    Configura el sistema de logging basado en 'settings.yaml'.

    Esta es la función principal que llamaremos desde fuera. Se encarga de:
    1. Cargar la configuración general (para obtener las prefs de logging).
    2. Definir un diccionario de configuración para el logging.
    3. Crear el directorio de logs si no existe.
    4. Aplicar la configuración usando logging.config.dictConfig.
    """
    global _logging_configured

    # Revisamos si ya configuramos el logging antes para no hacerlo múltiples veces.
    if _logging_configured:
        logging.log(logging.DEBUG, "El logging ya ha sido configurado previamente. Omitiendo reconfiguración.") # Usar logging.log con nivel explícito
        return

    # Como este módulo configura el logging, usamos print para los mensajes iniciales
    # o configuramos un logger temporal muy básico aquí mismo.
    print("INFO: Iniciando la configuración del sistema de logging...") # Usar print aquí es seguro

    try:
        # --- Cargar Configuración ---
        log_level_str = 'INFO' # Default
        log_filename = 'app.log' # Default
        log_dir_path_str = 'logs' # Default directory name
        project_root_dir = Path('.') # Default al directorio actual

        if config_loader: # Solo si pudimos importar el config_loader
            config = config_loader.get_config()
            if config:
                # Obtenemos las preferencias de logging desde el diccionario de config
                logging_settings = config.get('logging', {})
                log_level_str = logging_settings.get('level', 'INFO').upper()
                log_filename = logging_settings.get('log_file', 'app.log')
                # Podríamos hacer configurable la carpeta de logs también
                # log_dir_path_str = config.get('logging',{}).get('log_directory', 'logs')

                # Obtenemos la raíz del proyecto desde config_loader si está disponible
                if hasattr(config_loader, 'PROJECT_ROOT'):
                    project_root_dir = config_loader.PROJECT_ROOT
                else:
                    print("WARNING: config_loader no tiene PROJECT_ROOT definido. Usando directorio actual para logs.")

            else:
                print("WARNING: config_loader.get_config() devolvió None. Usando configuración de logging por defecto.")
        else:
             print("WARNING: config_loader no disponible. Usando configuración de logging por defecto.")


        # --- Preparar Nivel, Rutas y Directorio ---
        # Convertimos el nombre del nivel (ej: "INFO") a la constante numérica de logging (ej: logging.INFO)
        log_level_int = logging.getLevelName(log_level_str)
        if not isinstance(log_level_int, int):
            print(f"WARNING: Nivel de logging inválido '{log_level_str}' en config. Usando INFO.")
            log_level_int = logging.INFO

        # Construir ruta al directorio de logs y al archivo
        log_dir = project_root_dir / log_dir_path_str
        log_file_path = log_dir / log_filename

        # Asegurar que la carpeta 'logs' exista. ¡La creamos si no!
        log_dir.mkdir(parents=True, exist_ok=True)
        print(f"INFO: Directorio de logs asegurado/creado en: {log_dir}")

        # --- Definir la Configuración del Logging (El Diccionario Mágico) ---
        # Este diccionario le dice a `logging.config.dictConfig` cómo queremos todo.
        logging_config_dict = {
            'version': 1, # Requerido, siempre 1 por ahora.
            'disable_existing_loggers': False, # Importante dejarlo en False para no romper logs de librerías.
            'formatters': {
                # Cómo queremos que se vean los mensajes
                'standard': {
                    'format': '%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S',
                },
                'simple': {
                    'format': '%(levelname)s - [%(name)s] - %(message)s', # Un poco más de info que antes
                },
            },
            'handlers': {
                # A dónde enviamos los mensajes
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': 'INFO', # La consola mostrará INFO y niveles superiores (WARNING, ERROR...).
                    'formatter': 'simple', # Usamos el formato simple para la consola.
                    'stream': 'ext://sys.stdout', # Usamos la salida estándar.
                },
                'rotating_file': {
                    # ¡Nuestro guardián de archivos! Escribe en el archivo y lo rota.
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': log_level_int, # El archivo registrará desde el nivel que pusimos en config.
                    'formatter': 'standard', # Formato completo para el archivo.
                    'filename': str(log_file_path), # ¡La ruta al archivo! Importante convertir Path a string.
                    'maxBytes': 1024*1024*10, # Rotar cuando llegue a 10 MB.
                    'backupCount': 5, # Guardar hasta 5 archivos antiguos.
                    'encoding': 'utf-8', # Siempre usar utf-8 para evitar problemas.
                }
            },
            'loggers': {
                # Configuración para loggers específicos (útil para callar librerías ruidosas)
                 'schedule': { # Ejemplo: Para la librería schedule que usaremos
                     'level': 'INFO', # Mostrar solo INFO o superior de schedule
                     'handlers': ['console', 'rotating_file'],
                     'propagate': False, # No enviar también al root logger
                 },
                 'urllib3': { # urllib3 (usada por requests) puede ser muy verbosa en DEBUG
                     'level': 'WARNING',
                     'handlers': ['console', 'rotating_file'],
                     'propagate': False,
                 }
            },
            'root': {
                # Configuración por defecto para todos los demás loggers
                'level': log_level_int, # Nivel mínimo global
                'handlers': ['console', 'rotating_file'] # Enviar a ambos destinos
            }
        }

        # --- Aplicar la Configuración ---
        # ¡Le pasamos nuestro diccionario mágico a Python!
        logging.config.dictConfig(logging_config_dict)

        # Marcamos que ya hemos terminado para no volver a hacerlo.
        _logging_configured = True

        # ¡Ahora sí podemos usar el logger configurado!
        logger = logging.getLogger(__name__) # Obtenemos el logger de este módulo
        logger.info(f"Sistema de logging configurado. Nivel raíz: {log_level_str}. Archivo: {log_file_path}")

    except Exception as e:
        # Si algo falla DURANTE la configuración del logging, usamos print.
        print(f"ERROR CRÍTICO: Falló la configuración del logging: {e}")
        # Intentamos configurar algo básico para que al menos los errores se vean.
        logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        logging.exception("Detalles del error al configurar logging:")
        # Marcamos como no configurado para posibles reintentos o chequeos.
        _logging_configured = False
        # Quizás relanzar la excepción sea lo mejor para detener la app.
        # raise e

# --- Ejemplo de Uso (para probar este módulo solito) ---
# (El bloque if __name__ == '__main__': sería idéntico al que generamos la vez anterior)
if __name__ == '__main__':
    # Asumimos que existe un config/settings.yaml o usamos defaults.
    print("--- Probando la Configuración del Logging (ejecución directa) ---")
    setup_logging()

    test_logger = logging.getLogger("mi_prueba")
    print("\nEnviando mensajes de prueba a diferentes niveles...")

    test_logger.debug("Este es un mensaje DEBUG.")
    test_logger.info("Este es un mensaje INFO.")
    test_logger.warning("Este es un mensaje WARNING.")
    test_logger.error("Este es un mensaje ERROR.")
    test_logger.critical("Este es un mensaje CRITICAL.")

    # Probamos un logger de una librería configurada
    schedule_logger = logging.getLogger("schedule")
    schedule_logger.info("Simulando un INFO de la librería schedule (debería aparecer).")
    schedule_logger.debug("Simulando un DEBUG de la librería schedule (NO debería aparecer si root es INFO).")

    print(f"\nVerifica la consola y el archivo en la carpeta 'logs/' (ej: logs/app.log).")
    print("Deberías ver los mensajes formateados según la configuración.")
    # El nivel efectivo puede ser diferente para loggers específicos
    print(f"Nivel efectivo del logger raíz >= {logging.getLevelName(logging.getLogger().getEffectiveLevel())}")
    print(f"Nivel efectivo del logger 'schedule' >= {logging.getLevelName(logging.getLogger('schedule').getEffectiveLevel())}")
    print(f"Nivel configurado para la consola >= INFO")