# test_scraper.py
import sys
from pathlib import Path

# Asegurar que podamos importar desde el directorio raíz
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    print("Importando HTTPClient...")
    from src.utils.http_client import HTTPClient
    
    print("Importando ComputrabajoScraperImproved...")
    from src.scrapers.computrabajo_scraper_improved import ComputrabajoScraperImproved
    
    print("Inicializando HTTPClient...")
    http_client = HTTPClient()
    
    print("Inicializando ComputrabajoScraperImproved...")
    config = {'base_url': 'https://ec.computrabajo.com'}
    scraper = ComputrabajoScraperImproved(http_client=http_client, config=config)
    
    print("Configurando parámetros de búsqueda...")
    params = {'keywords': ['programador', 'python'], 'location': 'remote', 'process_detail_pages': False}
    
    print("Ejecutando búsqueda (esto puede tomar un tiempo)...")
    results = scraper.fetch_jobs(params)
    
    print(f"\nRESULTADOS: Se encontraron {len(results)} ofertas")
    
    if results:
        print("\nPrimera oferta encontrada:")
        for key, value in results[0].items():
            print(f"{key}: {value}")
    
    print("\nBúsqueda completada con éxito")
except Exception as e:
    print(f"ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
finally:
    # Asegurar que cerramos el cliente HTTP
    try:
        if 'http_client' in locals():
            http_client.close()
            print("Cliente HTTP cerrado")
    except:
        pass
