# -*- coding: utf-8 -*-
# /src/utils/config_loader.py

"""
Módulo para Cargar la Configuración del Proyecto.

Este módulo es nuestro "chico de los recados" para la configuración.
Se encarga de leer el archivo principal 'settings.yaml' con todas
las opciones y también carga los secretos (como las API keys) que
guardamos aparte en el archivo '.env' para mantenerlos seguros.
¡Así el resto del código puede pedirle la configuración fácilmente!

Funciones:
    load_config(): Carga la configuración la primera vez y la guarda.
    get_config(): Devuelve la configuración ya cargada (llama a load_config si es necesario).
    get_secret(key): Obtiene un secreto específico (ej: API Key) desde las variables de entorno.
"""

import yaml         # Necesitamos PyYAML para leer archivos .yaml (¡recuerda instalarlo!)
import os           # Para interactuar con el sistema operativo, sobre todo para leer variables de entorno
import logging      # Para registrar mensajes importantes o errores
from pathlib import Path  # La forma moderna y robusta de manejar rutas de archivos en Python
from dotenv import load_dotenv # La librería para cargar el archivo .env (¡instalar python-dotenv!)
from typing import Optional, Dict, Any # Para nuestros type hints

# Configuración básica del logger aquí, por si necesitamos loguear algo ANTES
# de que setup_logging() (de logging_config.py) sea llamado.
# Una vez setup_logging() se ejecute, esta configuración será reemplazada.
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Variables Globales del Módulo ---

# Aquí guardaremos la configuración una vez leída. Usamos None al principio.
# Esto es un truco simple (patrón Singleton a nivel módulo) para asegurarnos
# de que leemos los archivos del disco UNA SOLA VEZ, ¡más eficiente!
_config: Optional[Dict[str, Any]] = None

# --- Definición de Rutas ---

# Calculamos la ruta raíz del proyecto. ¡Esto es súper útil!
# Asumimos la estructura: project_root/src/utils/config_loader.py
# Path(__file__) es la ruta a ESTE archivo.
# .parent nos sube un nivel en la jerarquía de carpetas.
try:
    # Esta es la forma robusta de encontrar la raíz (tres niveles arriba de src/utils)
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    # Construimos la ruta al directorio de configuración /config/
    CONFIG_DIR = PROJECT_ROOT / "config"
    # Y las rutas a los archivos específicos que leeremos.
    SETTINGS_FILE = CONFIG_DIR / "settings.yaml"
    ENV_FILE = CONFIG_DIR / ".env" # El archivo real con secretos, NO .env.example
except NameError:
    # Si __file__ no está definido (puede pasar en algunos entornos interactivos),
    # usamos el directorio actual como fallback, aunque podría no ser correcto.
    logger.warning("__file__ no está definido. Usando directorio actual como base para buscar config. ¡Esto podría fallar!")
    PROJECT_ROOT = Path('.')
    CONFIG_DIR = PROJECT_ROOT / "config"
    SETTINGS_FILE = CONFIG_DIR / "settings.yaml"
    ENV_FILE = CONFIG_DIR / ".env"


# --- Funciones Principales ---

def load_config() -> Optional[Dict[str, Any]]:
    """
    Carga la configuración desde 'settings.yaml' y el archivo '.env'.

    Aplica el patrón singleton: solo carga los archivos la primera vez.
    Las llamadas siguientes devuelven la configuración ya almacenada en _config.

    Returns:
        Optional[Dict[str, Any]]: Diccionario con la config de settings.yaml,
                                  o None si ocurre un error crítico irrecuperable.

    Raises:
        FileNotFoundError: Si no se encuentra settings.yaml (considerado crítico).
        yaml.YAMLError: Si settings.yaml tiene errores de formato (crítico).
        Exception: Para otros errores inesperados durante la carga (crítico).
    """
    global _config
    # Si ya tenemos la config cargada en _config, ¡la devolvemos directamente!
    if _config is not None:
        logger.debug("Configuración ya cargada previamente. Devolviendo...")
        return _config

    # Si no, es la primera vez, ¡a cargarla!
    logger.info("Iniciando carga de configuración (primera vez)...")

    try:
        # --- 1. Cargar Secretos desde .env ---
        # Le decimos a python-dotenv dónde está nuestro archivo .env.
        if ENV_FILE.is_file():
            # override=True: si una variable ya existe en el entorno del S.O.,
            # la del archivo .env la sobreescribe. Útil en desarrollo.
            loaded = load_dotenv(dotenv_path=ENV_FILE, override=True)
            if loaded:
                logger.info(f"Variables de entorno cargadas desde: {ENV_FILE}")
            else:
                # Esto es raro, significa que encontró el archivo pero no cargó nada.
                logger.warning(f"Se encontró {ENV_FILE}, pero no se cargaron variables (¿vacío o formato incorrecto?).")
        else:
            # ¡Importante avisar! Sin .env, las APIs con clave fallarán.
            logger.warning(f"Archivo .env no encontrado en {ENV_FILE}. Las API keys y secretos no estarán disponibles.")
            # No lanzamos error aquí, quizás el usuario solo usa scrapers sin claves.

        # --- 2. Cargar Configuración Principal desde settings.yaml ---
        logger.info(f"Cargando configuración principal desde: {SETTINGS_FILE}")
        if not SETTINGS_FILE.is_file():
            # Consideramos esto un error crítico. Sin settings, no sabemos qué hacer.
            logger.error(f"¡ERROR CRÍTICO! No se encontró el archivo de configuración principal: {SETTINGS_FILE}")
            # Lanzamos la excepción para que el programa principal sepa que no puede continuar.
            raise FileNotFoundError(f"Archivo de configuración no encontrado: {SETTINGS_FILE}")

        # Abrimos y leemos el archivo YAML. 'safe_load' es la forma segura.
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as file:
            loaded_yaml_config = yaml.safe_load(file)
            if not loaded_yaml_config: # Si el archivo existe pero está vacío o es inválido
                 logger.warning(f"El archivo {SETTINGS_FILE} está vacío o no es un YAML válido.")
                 _config = {} # Usamos un dict vacío como config en este caso.
            else:
                 _config = loaded_yaml_config # ¡Guardamos la config leída en nuestra variable global!
                 logger.info("Archivo settings.yaml cargado y parseado exitosamente.")

        # Aquí podríamos añadir validaciones más profundas de la estructura de _config si quisiéramos.

        return _config # Devolvemos la configuración recién cargada.

    except FileNotFoundError as e:
        logger.exception("Error: Archivo de configuración no encontrado.")
        raise e # Relanzamos para que quede claro el error crítico.
    except yaml.YAMLError as e:
        logger.error(f"Error de formato en el archivo YAML: {SETTINGS_FILE}.")
        logger.exception("Detalles del error de YAML:")
        raise e # Relanzamos, un YAML mal formado es crítico.
    except Exception as e:
        logger.error(f"Error inesperado al cargar la configuración.")
        logger.exception("Detalles del error inesperado:")
        _config = None # Asegurarnos de que _config quede None si falla la carga completa.
        raise e # Relanzamos para indicar el fallo crítico.


def get_config() -> Optional[Dict[str, Any]]:
    """
    Obtiene el diccionario de configuración cargado.

    Llama a load_config() si la configuración aún no ha sido cargada.
    Es la función que usarán normalmente los otros módulos.

    Returns:
        Optional[Dict[str, Any]]: El diccionario de configuración, o None si falló la carga.
    """
    # Simplemente llama a load_config, que se encarga de la lógica de cargar solo una vez.
    config_data = load_config()
    # Añadimos una verificación extra por si acaso load_config falló de forma inesperada y devolvió None.
    if config_data is None:
        logger.critical("¡get_config() recibió None de load_config! La configuración no está disponible.")
        # En un caso real, podríamos querer lanzar un error aquí también.
        # raise RuntimeError("Configuración no disponible.")
    return config_data


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Obtiene un valor "secreto" desde las variables de entorno.

    Es la forma recomendada y segura para obtener API keys, contraseñas, etc.,
    que fueron cargadas previamente desde el archivo .env por load_dotenv().

    Args:
        key (str): El nombre de la variable de entorno a buscar (ej: "ADZUNA_APP_KEY").
        default (Optional[str], optional): Valor a devolver si la variable no se encuentra.
                                           Por defecto es None.

    Returns:
        Optional[str]: El valor de la variable de entorno si existe, o el valor default.
                       Devuelve None si no existe y default es None.
    """
    # Usamos os.getenv(), que es la forma estándar de leer variables de entorno.
    # Es seguro porque devuelve None (o el default) si la variable no existe, no da error.
    value = os.getenv(key, default)

    # Añadimos un log útil si no encontramos una clave esperada.
    if value is None and default is None:
        logger.warning(f"Variable de entorno/secreto '{key}' no encontrada y no se especificó valor por defecto.")
    elif value == default and default is not None:
         logger.debug(f"Variable de entorno/secreto '{key}' no encontrada. Usando valor por defecto.")
    else:
         # ¡NUNCA loguear el valor del secreto! Solo confirmar que se encontró.
         logger.debug(f"Variable de entorno/secreto '{key}' encontrada.")

    # Una comprobación extra útil: ¿pusimos el placeholder en lugar de la clave real en .env?
    placeholders = ["TU_", "YOUR_", "PON_TU_", "INSERT_YOUR_"]
    if isinstance(value, str) and any(value.startswith(p) for p in placeholders):
        logger.error(f"¡ALERTA! El valor para '{key}' ('{value}') parece un placeholder. "
                     f"¿Olvidaste poner la clave real en tu archivo .env?")
        # Podríamos incluso devolver None o lanzar un error aquí para más seguridad.
        # return None

    return value

# --- Ejemplo de Uso (Solo si corres este script directamente) ---
if __name__ == '__main__':
    # Este bloque ayuda a probar que el módulo carga bien la config.
    print("--- Probando el Cargador de Configuración (config_loader.py) ---")
    # Necesitarás tener 'config/settings.yaml' y 'config/.env' creados para que funcione bien.

    try:
        # 1. Intentamos cargar la configuración completa.
        configuracion = get_config()
        print("\n--- Configuración Cargada desde settings.yaml ---")
        if configuracion:
             # Imprimimos algunas partes para verificar.
             print(f"Nivel de Logging: {configuracion.get('logging', {}).get('level', 'No especificado')}")
             print(f"Nombre BD: {configuracion.get('data_storage', {}).get('sqlite', {}).get('database_name', 'No especificado')}")
             print(f"Exportar CSV?: {configuracion.get('data_storage', {}).get('csv', {}).get('export_enabled', 'No especificado')}")
             print(f"Fuentes API keys: {list(configuracion.get('sources', {}).get('apis', {}).keys())}")
             print(f"Fuentes Scraper keys: {list(configuracion.get('sources', {}).get('scrapers', {}).keys())}")
        else:
            print("La configuración principal (settings.yaml) no se pudo cargar (es None).")

        # 2. Intentamos obtener secretos (que deberían haberse cargado desde .env).
        print("\n--- Probando Acceso a Secretos (desde .env vía get_secret) ---")
        adzuna_id = get_secret("ADZUNA_APP_ID")
        adzuna_key = get_secret("ADZUNA_APP_KEY")
        jooble_key = get_secret("JOOBLE_API_KEY")
        clave_inventada = get_secret("MI_CLAVE_SECRETA_INEXISTENTE", default="valor_default_test")

        # Mostramos solo si se encontraron o no, NUNCA el valor real.
        print(f"ADZUNA_APP_ID encontrado: {'Sí' if adzuna_id and not any(adzuna_id.startswith(p) for p in ['TU_']) else 'No o Placeholder'}")
        print(f"ADZUNA_APP_KEY encontrado: {'Sí' if adzuna_key and not any(adzuna_key.startswith(p) for p in ['TU_']) else 'No o Placeholder'}")
        print(f"JOOBLE_API_KEY encontrado: {'Sí' if jooble_key and not any(jooble_key.startswith(p) for p in ['TU_']) else 'No o Placeholder'}")
        print(f"CLAVE_INEXISTENTE: '{clave_inventada}' (devolvió el default)")

        # 3. Probamos a llamar get_config() de nuevo para ver el mensaje de "ya cargada".
        print("\n--- Llamando a get_config() de nuevo ---")
        config_2 = get_config()
        if config_2 is configuracion: # Comprueba si es el MISMO objeto en memoria
             print("Confirmado: get_config() devolvió la instancia ya cargada (eficiencia Singleton).")
        else:
             print("Algo raro pasó, get_config() devolvió un objeto diferente la segunda vez.")

    except FileNotFoundError:
        print("\nERROR: No se encontró el archivo 'config/settings.yaml'. Crea uno para probar.")
    except Exception as e:
        print(f"\n--- Ocurrió un error durante la prueba ---")
        # Imprimimos el error para diagnóstico.
        import traceback
        traceback.print_exc()