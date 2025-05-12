#!/usr/bin/env python
# -*- coding: utf-8 -*-
# test_mejoras.py

"""
Script para probar las mejoras implementadas en el buscador de empleo inteligente.
Este script ejecuta y compara el pipeline original y el mejorado para verificar 
que las mejoras aumentan el número de fuentes exitosas y ofertas encontradas.
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path

# Asegurar que podamos importar desde el directorio raíz
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_test():
    print("=" * 70)
    print("Test de Mejoras para el Buscador de Empleo Inteligente")
    print("=" * 70)
    
    # Crear directorio para resultados de prueba si no existe
    results_dir = project_root / "test_results"
    results_dir.mkdir(exist_ok=True)
    
    # Timestamp para los archivos de resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Ejecutar pipeline original
    print("\n1. Ejecutando pipeline original...")
    start_original = time.time()
    from src.main import run_job_search_pipeline as original_pipeline
    original_result = original_pipeline()
    time_original = time.time() - start_original
    print(f"   Completado en {time_original:.2f} segundos.")
    
    # Breve pausa para asegurar que los recursos se liberan
    time.sleep(2)
    
    # Ejecutar pipeline mejorado
    print("\n2. Ejecutando pipeline mejorado...")
    start_improved = time.time()
    from src.main_improved import run_job_search_pipeline as improved_pipeline
    improved_result = improved_pipeline()
    time_improved = time.time() - start_improved
    print(f"   Completado en {time_improved:.2f} segundos.")
    
    # Extraer estadísticas de los archivos CSV
    csv_dir = project_root / "data" / "historico"
    
    def get_latest_csv_stats(prefix):
        # Obtener el CSV más reciente que comienza con el prefijo
        files = list(csv_dir.glob(f"{prefix}*.csv"))
        if not files:
            return {"error": f"No se encontraron archivos {prefix}*.csv"}
        
        latest_file = max(files, key=os.path.getmtime)
        
        # Obtener estadísticas básicas
        line_count = sum(1 for _ in open(latest_file, 'r', encoding='utf-8'))
        file_size = os.path.getsize(latest_file)
        
        return {
            "filename": latest_file.name,
            "size_bytes": file_size,
            "line_count": line_count,
            "last_modified": datetime.fromtimestamp(os.path.getmtime(latest_file)).isoformat()
        }
    
    original_stats = {
        "tiempo_ejecucion": time_original,
        "ofertas_todas": get_latest_csv_stats("ofertas_"),
        "ofertas_filtradas": get_latest_csv_stats("ofertas_filtradas_")
    }
    
    improved_stats = {
        "tiempo_ejecucion": time_improved,
        "ofertas_todas": get_latest_csv_stats("ofertas_"),
        "ofertas_filtradas": get_latest_csv_stats("ofertas_filtradas_"),
        "pipeline_summary": improved_result.get("summary", {})
    }
    
    # Guardar resultados
    results = {
        "timestamp": timestamp,
        "original": original_stats,
        "improved": improved_stats
    }
    
    results_file = results_dir / f"comparacion_mejoras_{timestamp}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    # Mostrar comparación
    print("\n" + "=" * 70)
    print("RESULTADOS DE LA COMPARACIÓN")
    print("=" * 70)
    
    original_lines = original_stats["ofertas_filtradas"].get("line_count", 0)
    improved_lines = improved_stats["ofertas_filtradas"].get("line_count", 0)
    
    if original_lines and improved_lines:
        improvement = ((improved_lines - original_lines) / original_lines) * 100
        print(f"\nOfertas filtradas (original): {original_lines - 1} registros")  # -1 por la cabecera
        print(f"Ofertas filtradas (mejorado): {improved_lines - 1} registros")  # -1 por la cabecera
        print(f"Mejora: {improvement:.1f}% más ofertas relevantes")
    
    print(f"\nTiempo de ejecución (original): {time_original:.2f} segundos")
    print(f"Tiempo de ejecución (mejorado): {time_improved:.2f} segundos")
    
    print(f"\nDetalles completos guardados en: {results_file}")
    print("=" * 70)

if __name__ == "__main__":
    run_test()
