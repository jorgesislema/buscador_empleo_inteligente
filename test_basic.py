# test_basic.py
import sys
import json
from pathlib import Path

# Asegurar que podamos importar desde el directorio raíz
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def print_separator():
    print("\n" + "=" * 50)

def run_test():
    print_separator()
    print("TEST BÁSICO DEL BUSCADOR DE EMPLEO")
    print_separator()
    
    # 1. Prueba de importación de módulos básicos
    print("\n1. Importando módulos básicos...")
    try:
        from src.utils import config_loader
        print("✓ config_loader importado correctamente")
        
        from src.utils import logging_config
        print("✓ logging_config importado correctamente")
        
        from src.utils.http_client import HTTPClient
        print("✓ HTTPClient importado correctamente")
        
        from src.persistence.database_manager import DatabaseManager
        print("✓ DatabaseManager importado correctamente")
        
        from src.core.job_filter import JobFilter
        print("✓ JobFilter importado correctamente")
    except Exception as e:
        print(f"✗ Error importando módulos: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 2. Prueba de carga de configuración
    print("\n2. Cargando configuración...")
    try:
        config = {}
        # Intentar cargar la configuración de algunas formas
        try:
            config = config_loader.load_settings()
            print("✓ Configuración cargada con load_settings()")
        except:
            # Si no existe load_settings, probamos get_config
            try:
                config = config_loader.get_config()
                print("✓ Configuración cargada con get_config()")
            except:
                # Si no hay método disponible, leer el archivo manualmente
                import yaml
                with open('config/settings.yaml', 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                print("✓ Configuración cargada leyendo el archivo YAML directamente")
        
        # Verificar si hay datos en la configuración
        if config:
            print(f"✓ Configuración contiene datos: {len(config)} secciones principales")
        else:
            print("✗ La configuración está vacía")
    except Exception as e:
        print(f"✗ Error cargando configuración: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. Prueba de conexión HTTP básica
    print("\n3. Probando conexión HTTP...")
    try:
        http_client = HTTPClient()
        response = http_client.get("https://www.google.com")
        if response and response.status_code == 200:
            print(f"✓ Conexión HTTP exitosa: status_code={response.status_code}")
        else:
            print(f"✗ Conexión HTTP fallida: {response}")
    except Exception as e:
        print(f"✗ Error probando conexión HTTP: {e}")
        import traceback
        traceback.print_exc()
    
    # 4. Verificar fuentes disponibles
    print("\n4. Verificando fuentes disponibles...")
    try:
        # Verificar APIs
        from src.apis.base_api import BaseAPIClient
        apis = [
            "adzuna_client", 
            "adzuna_client_improved",
            "arbeitnow_client",
            "jooble_client",
            "remoteok_client"
        ]
        
        for api_name in apis:
            try:
                __import__(f"src.apis.{api_name}")
                print(f"✓ API {api_name} disponible")
            except ImportError:
                print(f"✗ API {api_name} no disponible")
        
        # Verificar scrapers
        from src.scrapers.base_scraper import BaseScraper
        scrapers = [
            "linkedin_scraper",
            "linkedin_scraper_improved",
            "infojobs_scraper",
            "infojobs_scraper_improved",
            "computrabajo_scraper",
            "computrabajo_scraper_improved"
        ]
        
        for scraper_name in scrapers:
            try:
                __import__(f"src.scrapers.{scraper_name}")
                print(f"✓ Scraper {scraper_name} disponible")
            except ImportError:
                print(f"✗ Scraper {scraper_name} no disponible")
    except Exception as e:
        print(f"✗ Error verificando fuentes: {e}")
        import traceback
        traceback.print_exc()
    
    print_separator()
    print("PRUEBA BÁSICA COMPLETADA")
    print_separator()

if __name__ == "__main__":
    run_test()
