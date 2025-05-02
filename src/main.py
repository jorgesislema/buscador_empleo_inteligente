# En otro archivo, por ejemplo, src/main.py

import os # Necesario para getenv si usas secretos directamente
from src.utils import config_loader # Importamos nuestro módulo

# Cargamos/obtenemos la configuración al inicio
try:
    config = config_loader.get_config()

    # Ahora puedes acceder a la configuración como un diccionario
    log_level = config['logging']['level']
    db_name = config['data_storage']['sqlite']['database_name']
    keywords = config['job_titles'] + config['tools_technologies'] + config['topics'] # Combinamos keywords
    locations = config['locations']

    print(f"Se usarán las keywords: {keywords}")
    print(f"Se buscará en las ubicaciones: {locations}")

    # Para obtener un secreto (ej: API key de Adzuna)
    # Opción 1: Usando la función helper get_secret (recomendado)
    adzuna_api_key = config_loader.get_secret("ADZUNA_APP_KEY")
    if not adzuna_api_key:
        print("Advertencia: No se encontró la API Key de Adzuna en .env")
        # Aquí podrías decidir desactivar Adzuna o detener la ejecución
    else:
        # Pasar la clave SOLO al cliente de Adzuna cuando sea necesario
        print("API Key de Adzuna lista para usar.")
        # adzuna_client.inicializar(api_key=adzuna_api_key) # Ejemplo

    # Opción 2: Usando os.getenv directamente (funciona porque load_dotenv ya fue llamado)
    # adzuna_app_id = os.getenv("ADZUNA_APP_ID")
    # print(f"Adzuna App ID obtenido directamente: {'Sí' if adzuna_app_id else 'No'}")

except Exception as e:
    print(f"Error crítico al cargar la configuración. No se puede continuar. Error: {e}")
    # Terminar la ejecución o manejar el error apropiadamente