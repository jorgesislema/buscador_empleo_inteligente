# -*- coding: utf-8 -*-
# /src/utils/config_loader.py

"""
Módulo para Cargar la Configuración del Proyecto.

Este módulo se encarga de leer el archivo de configuración principal 'settings.yaml'
y de cargar las variables de entorno (especialmente secretos como API keys)
desde el archivo '.env'. Utiliza las librerías PyYAML y python-dotenv.

Funciones:
    load_config(): Carga la configuración y la devuelve como un diccionario.
                   Utiliza un patrón singleton simple para cargarla solo una vez.
    get_config(): Devuelve la configuración ya cargada. Es un alias para load_config().
    get_secret(key): Obtiene un secreto específico desde las variables de entorno.
"""

import yaml         # Necesitamos PyYAML para leer archivos .yaml
import os           # Para interactuar con el sistema operativo, especialmente para leer variables de entorno
import logging      # Para registrar información o errores durante la carga
from pathlib import Path  # Para construir rutas de archivo de forma robusta e independiente del S.O.
from dotenv import load_dotenv # Necesitamos python-dotenv para cargar el archivo .env

# Configuración del logger para este módulo
# Usaremos un logger básico aquí por si necesitamos registrar algo ANTES de que
# la configuración de logging principal (de logging_config.py) esté lista.
# En una aplicación más compleja, se podría inyectar el logger principal.
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO) # Configuración básica temporal

# --- Variables Globales del Módulo ---

# Variable para almacenar la configuración una vez cargada (Patrón Singleton simple)
# La idea es leer los archivos solo una vez al inicio y luego reutilizar la configuración.
_config = None

# --- Definición de Rutas ---

# Obtenemos la ruta al directorio raíz del proyecto.
# Asumimos que este archivo (config_loader.py) está en src/utils/.
# Path(__file__) -> Ruta a este archivo.
# .parent -> Sube un nivel (a src/utils/)
# .parent -> Sube otro nivel (a src/)
# .parent -> Sube otro nivel (a la raíz del proyecto)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Construimos la ruta al directorio de configuración
CONFIG_DIR = PROJECT_ROOT / "config"

# Construimos las rutas completas a los archivos de configuración
SETTINGS_FILE = CONFIG_DIR / "settings.yaml"
ENV_FILE = CONFIG_DIR / ".env" # Ojo: usamos .env, NO .env.example

# --- Funciones Principales ---

def load_config() -> dict:
    """
    Carga la configuración desde 'settings.yaml' y el archivo '.env'.

    Utiliza un patrón singleton: la configuración se carga solo la primera vez
    que se llama a esta función. Las llamadas posteriores devuelven la
    configuración ya cargada.

    Returns:
        dict: Un diccionario que contiene la configuración del archivo settings.yaml.
              Retorna None si ocurre un error grave durante la carga.

    Raises:
        FileNotFoundError: Si no se encuentra el archivo settings.yaml.
        yaml.YAMLError: Si hay un error al parsear el archivo settings.yaml.
        Exception: Para otros errores inesperados durante la carga.
    """
    global _config
    # Si la configuración ya fue cargada (_config no es None), la devolvemos directamente.
    if _config is not None:
        logger.debug("Configuración ya cargada. Devolviendo la instancia existente.")
        return _config

    logger.info("Iniciando la carga de la configuración...")

    try:
        # --- Cargar variables de entorno desde .env ---
        # load_dotenv buscará un archivo .env en el directorio actual o subiendo niveles.
        # Es más robusto especificar la ruta exacta con dotenv_path.
        # find_dotenv() podría ser otra opción, pero especificar la ruta es más explícito.
        if ENV_FILE.is_file():
            # Carga las variables del archivo .env en las variables de entorno del sistema.
            # override=True significa que si una variable ya existe en el entorno, será sobrescrita
            # por la del archivo .env. Puede ser útil en desarrollo.
            loaded_dotenv = load_dotenv(dotenv_path=ENV_FILE, override=True)
            if loaded_dotenv:
                logger.info(f"Archivo .env encontrado y cargado desde: {ENV_FILE}")
            else:
                # Esto puede pasar si el archivo .env está vacío o tiene algún problema.
                logger.warning(f"Se encontró el archivo .env en {ENV_FILE}, pero no se cargaron variables.")
        else:
            # Es importante advertir si no se encuentra .env, ya que contendrá secretos.
            logger.warning(f"Archivo .env no encontrado en {ENV_FILE}. Asegúrate de crearlo si necesitas API keys u otros secretos.")
            # La aplicación puede continuar, pero fallará si intenta usar secretos no definidos.

        # --- Cargar configuración desde settings.yaml ---
        logger.info(f"Intentando cargar settings desde: {SETTINGS_FILE}")
        if not SETTINGS_FILE.is_file():
            # Error crítico si no encontramos el archivo de configuración principal.
            logger.error(f"¡Error Crítico! No se encontró el archivo de configuración: {SETTINGS_FILE}")
            raise FileNotFoundError(f"No se encontró el archivo de configuración: {SETTINGS_FILE}")

        # Abrimos y leemos el archivo YAML.
        # Usamos 'with' para asegurarnos de que el archivo se cierre correctamente.
        # 'r' es para modo lectura, 'encoding='utf-8'' es importante para soportar caracteres especiales.
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as file:
            # yaml.safe_load es preferible a yaml.load por seguridad.
            # Parsea el contenido del archivo YAML en una estructura de datos Python (normalmente un diccionario).
            loaded_yaml_config = yaml.safe_load(file)
            if not loaded_yaml_config:
                 logger.warning(f"El archivo settings.yaml ({SETTINGS_FILE}) parece estar vacío o no contiene datos válidos.")
                 _config = {} # Asignamos un diccionario vacío para evitar None
            else:
                 _config = loaded_yaml_config # Guardamos la configuración cargada en nuestra variable global
            logger.info("Archivo settings.yaml cargado exitosamente.")

        # Aquí podrías añadir validaciones más complejas sobre la configuración cargada si fuera necesario.
        # Por ejemplo, verificar que ciertas claves esperadas existen.
        # ej: if 'sources' not in _config: raise ValueError("La clave 'sources' falta en settings.yaml")

        # Devolvemos la configuración cargada.
        return _config

    except FileNotFoundError as e:
        # Relanzamos la excepción específica de archivo no encontrado.
        logger.exception("Error de archivo no encontrado durante la carga de configuración.") # log exception info
        raise e
    except yaml.YAMLError as e:
        # Error al parsear el YAML, puede ser por sintaxis incorrecta.
        logger.error(f"Error al parsear el archivo YAML: {SETTINGS_FILE}. Detalles: {e}")
        logger.exception("Detalles del error de YAML:") # log exception info
        raise e # Relanzamos la excepción específica de YAML.
    except Exception as e:
        # Captura cualquier otro error inesperado durante el proceso.
        logger.error(f"Ocurrió un error inesperado al cargar la configuración: {e}")
        logger.exception("Detalles del error inesperado:") # log exception info
        # En lugar de devolver None, relanzar la excepción puede ser mejor
        # para detener la ejecución si la configuración es crucial.
        raise e # Relanzamos la excepción general.

def get_config() -> dict:
    """
    Función de conveniencia para obtener la configuración.

    Simplemente llama a load_config(). Si la configuración no ha sido cargada,
    la cargará. Si ya fue cargada, devolverá la instancia existente.

    Returns:
        dict: El diccionario de configuración.
    """
    # Llama a load_config(), que maneja la lógica de carga única (singleton).
    config_data = load_config()
    if config_data is None:
        # Esto no debería pasar si load_config relanza excepciones, pero por si acaso.
        logger.critical("La configuración no pudo ser cargada y es None. Revisar errores previos.")
        # Podríamos retornar un diccionario vacío o lanzar un error aquí.
        # Lanzar un error es más seguro si la config es indispensable.
        raise ValueError("La configuración no pudo ser cargada correctamente.")
    return config_data

def get_secret(key: str, default: str = None) -> str | None:
    """
    Obtiene un valor secreto (variable de entorno).

    Busca la clave proporcionada en las variables de entorno del sistema.
    Es la forma segura de obtener API keys y otros secretos cargados desde .env.

    Args:
        key (str): El nombre de la variable de entorno a buscar (ej: "ADZUNA_APP_KEY").
        default (str, optional): Valor a devolver si la variable no se encuentra.
                                 Por defecto es None.

    Returns:
        str | None: El valor de la variable de entorno si se encuentra,
                    o el valor 'default' si no se encuentra.
    """
    # os.getenv() busca la variable de entorno. Es la forma estándar y segura.
    # No falla si no la encuentra, simplemente devuelve None (o el valor 'default' que le pasemos).
    value = os.getenv(key, default)
    if value is None and default is None:
        # Si la variable no se encontró y no se proveyó un default,
        # podemos advertir al usuario, ya que podría ser un problema.
        logger.warning(f"La variable de entorno secreta '{key}' no fue encontrada y no se estableció un valor por defecto.")
    elif value == default:
         logger.debug(f"La variable de entorno secreta '{key}' no fue encontrada. Usando valor por defecto.")
    else:
        # Por seguridad, NO registramos el valor del secreto encontrado.
         logger.debug(f"Variable de entorno secreta '{key}' encontrada.")

    # Muy importante: Verificar si el valor encontrado es el placeholder del .env.example
    # Esto ayuda a detectar si el usuario olvidó poner la clave real en .env
    placeholders = ["TU_", "YOUR_", "PON_TU_"] # Lista de prefijos comunes de placeholders
    if isinstance(value, str) and any(value.startswith(p) for p in placeholders):
        logger.error(f"¡Alerta de Seguridad! La variable de entorno '{key}' parece contener un valor placeholder ('{value}'). "
                     f"Asegúrate de haber configurado la clave real en tu archivo .env")
        # Podríamos decidir lanzar un error aquí para detener la ejecución si una clave real es indispensable.
        # raise ValueError(f"La clave para '{key}' no parece estar configurada correctamente en .env")

    return value

# --- Ejemplo de Uso (Solo se ejecuta si corres este script directamente) ---
if __name__ == '__main__':
    # Este bloque es útil para probar el módulo de forma aislada.
    print("--- Probando el Cargador de Configuración ---")

    # Intentamos cargar la configuración
    try:
        configuracion = get_config() # Usamos la función de conveniencia

        # Imprimimos algunas partes de la configuración cargada desde YAML
        print("\n--- Configuración Cargada desde settings.yaml ---")
        if configuracion: # Verificamos que no sea None (aunque ahora lanzamos error antes)
             print(f"Nivel de Logging: {configuracion.get('logging', {}).get('level', 'No especificado')}")
             print(f"Base de Datos SQLite: {configuracion.get('data_storage', {}).get('sqlite', {}).get('database_name', 'No especificado')}")
             print(f"APIs Habilitadas: {list(configuracion.get('sources', {}).get('apis', {}).keys())}") # Muestra nombres de APIs configuradas
             print(f"Scrapers Habilitados: {list(configuracion.get('sources', {}).get('scrapers', {}).keys())}") # Muestra nombres de Scrapers configurados
             print(f"Primera Keyword: {configuracion.get('job_titles', [''])[0] if configuracion.get('job_titles') else 'No especificado'}")
             print(f"Primera Ubicación: {configuracion.get('locations', [''])[0] if configuracion.get('locations') else 'No especificado'}")
        else:
            print("La configuración no se pudo cargar (es None).")


        # Intentamos obtener algunos secretos (cargados desde .env)
        print("\n--- Probando Acceso a Secretos (desde .env via os.getenv) ---")
        adzuna_id = get_secret("ADZUNA_APP_ID")
        adzuna_key = get_secret("ADZUNA_APP_KEY")
        jooble_key = get_secret("JOOBLE_API_KEY")
        clave_inexistente = get_secret("ESTA_CLAVE_NO_EXISTE", default="ValorPorDefecto")

        # Mostramos solo si se encontraron o no, NUNCA el valor de la clave.
        print(f"ADZUNA_APP_ID encontrado: {'Sí' if adzuna_id else 'No'}")
        print(f"ADZUNA_APP_KEY encontrado: {'Sí' if adzuna_key else 'No'}")
        print(f"JOOBLE_API_KEY encontrado: {'Sí' if jooble_key else 'No'}")
        print(f"ESTA_CLAVE_NO_EXISTE: {clave_inexistente}")

    except Exception as e:
        print(f"\n--- Ocurrió un error durante la prueba ---")
        print(e)