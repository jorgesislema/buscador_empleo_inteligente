# test_pipeline.py
import sys
from pathlib import Path
import time
import json

# Asegurar que podamos importar desde el directorio raíz
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_test():
    print("=" * 70)
    print("Prueba de Pipeline para el Buscador de Empleo Inteligente")
    print("=" * 70)
    
    # Ejecutar pipeline con número limitado de fuentes
    try:
        print("\nCargando configuración...")
        from src.utils import config_loader
        config = config_loader.load_settings()
        
        # Modificar configuración para usar menos fuentes y hacer la prueba más rápida
        print("Modificando configuración para prueba rápida...")
        config['sources'] = {
            'adzuna': True,
            'linkedin': False,
            'infojobs': False,
            'jooble': True,
            'computrabajo': True,
            'remoteok': True
        }
        
        # Modificar parámetros de búsqueda
        config['search_params'] = {
            'query': 'python developer',
            'location': 'remote',
            'max_pages': 2,
            'max_results': 5
        }
        
        print("\nEjecutando pipeline principal...")
        start_time = time.time()
        
        # Importar y ejecutar pipeline
        from src.main import run_job_search_pipeline
        results = run_job_search_pipeline(config)
        
        elapsed_time = time.time() - start_time
        print(f"Pipeline completado en {elapsed_time:.2f} segundos")
        
        # Mostrar resultados
        if isinstance(results, dict):
            print(f"\nResultados: {json.dumps(results, indent=2)}")
        else:
            print(f"\nResultados: {results}")
        
    except Exception as e:
        print(f"\nERROR en la ejecución del pipeline: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
