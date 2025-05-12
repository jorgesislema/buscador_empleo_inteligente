# -*- coding: utf-8 -*-
# /scripts/run_super_scraper.py

"""
Script para ejecutar el super pipeline mejorado de búsqueda de empleo.
Este script ejecuta todas las mejoras implementadas en el buscador de empleo:
- Cliente HTTP mejorado con mejor manejo de errores
- Paralelismo optimizado
- Scrapers mejorados (LinkedIn, etc.)
- Mejores estrategias de búsqueda
"""

import os
import sys
import time
import logging
import json
from pathlib import Path
from datetime import datetime

# Asegurar que podamos importar desde el directorio raíz
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.utils import logging_config
    from src.super_pipeline import run_job_search_pipeline_super
    from src.main_improved import run_job_search_pipeline as run_job_search_pipeline_improved
    from src.main import run_job_search_pipeline as run_job_search_pipeline_original
except ImportError as e:
    print(f"Error en las importaciones: {e}")
    print("Asegúrate de que estás ejecutando desde la carpeta correcta.")
    sys.exit(1)

# Configurar logging
logging_config.setup_logging()
logger = logging.getLogger("test_comparativo")

def run_test_comparativo():
    """Ejecuta un test comparativo entre las diferentes versiones del pipeline"""
    print("\n" + "=" * 80)
    print("EJECUTANDO TEST COMPARATIVO DE BUSCADOR DE EMPLEO INTELIGENTE")
    print("=" * 80)
    print("\nEste test comparará los resultados entre las diferentes versiones:")
    print("1. Pipeline original (main.py)")
    print("2. Pipeline mejorado (main_improved.py)")
    print("3. Super Pipeline (super_pipeline.py - todas las mejoras)")
    print("\nEl test medirá:")
    print("- Tiempo de ejecución total")
    print("- Cantidad de ofertas encontradas (total y filtradas)")
    print("- Fuentes exitosas vs fallidas")
    print("- Robustez ante errores")
    print("\nLos resultados se guardarán en data/resultados_comparativa.json")
    
    resultados = {
        "fecha_ejecución": datetime.now().isoformat(),
        "resultados": {}
    }
    
    # Ejecutar cada versión del pipeline
    pipelines = [
        ("original", run_job_search_pipeline_original),
        ("mejorado", run_job_search_pipeline_improved),
        ("super", run_job_search_pipeline_super)
    ]
    
    for nombre, funcion in pipelines:
        print(f"\n{'-' * 40}")
        print(f"Ejecutando pipeline {nombre}...")
        print(f"{'-' * 40}")
        
        inicio = time.time()
        
        try:
            resultado = funcion()
            
            fin = time.time()
            duracion = fin - inicio
              # Guardar resultados
            if isinstance(resultado, dict):
                # Extraer métricas específicas según la versión del pipeline
                if nombre == "super":
                    # El super pipeline tiene estructura más detallada con stats
                    resultados["resultados"][nombre] = {
                        "estado": resultado.get("status", "desconocido"),
                        "mensaje": resultado.get("message", ""),
                        "tiempo_segundos": duracion,
                        "ofertas_filtradas": resultado.get("filtered_jobs", 0) if "filtered_jobs" in resultado else resultado.get("stats", {}).get("jobs", {}).get("total_filtered", 0),
                        "ofertas_totales": resultado.get("processed_jobs", 0) if "processed_jobs" in resultado else resultado.get("stats", {}).get("jobs", {}).get("total_raw", 0),
                        "fuentes_exitosas": resultado.get("stats", {}).get("sources", {}).get("successful", 0),
                        "fuentes_fallidas": resultado.get("stats", {}).get("sources", {}).get("failed", 0),
                        "modulos_mejorados": resultado.get("stats", {}).get("improved_modules", {}),
                        "errores": resultado.get("stats", {}).get("error_summary", {})
                    }
                else:
                    # Pipelines original y mejorado tienen estructura más simple
                    resultados["resultados"][nombre] = {
                        "estado": resultado.get("status", "desconocido"),
                        "mensaje": resultado.get("message", ""),
                        "tiempo_segundos": duracion,
                        "ofertas_filtradas": resultado.get("filtered_jobs", 0) if "filtered_jobs" in resultado else resultado.get("summary", {}).get("filtered_jobs", 0),
                        "ofertas_totales": resultado.get("processed_jobs", 0) if "processed_jobs" in resultado else resultado.get("summary", {}).get("raw_jobs_collected", 0),
                        "fuentes_exitosas": resultado.get("summary", {}).get("successful_sources", 0),
                        "fuentes_fallidas": resultado.get("summary", {}).get("failed_sources", 0)
                    }
            else:
                resultados["resultados"][nombre] = {
                    "estado": "ejecutado",
                    "tiempo_segundos": duracion,
                    "nota": "La función no devolvió un diccionario de resultados"
                }
            
            print(f"\nPipeline {nombre} completado en {duracion:.2f} segundos.")
            
        except Exception as e:
            fin = time.time()
            duracion = fin - inicio
            
            print(f"\n⛔ Error ejecutando pipeline {nombre}: {e}")
            
            resultados["resultados"][nombre] = {
                "estado": "error",
                "mensaje": str(e),
                "tiempo_segundos": duracion
            }
    
    # Guardar resultados en un archivo JSON
    resultados_file = project_root / "data" / "resultados_comparativa.json"
    
    try:
        with open(resultados_file, 'w', encoding='utf-8') as f:
            json.dump(resultados, f, indent=2, ensure_ascii=False)
        
        print(f"\nResultados guardados en {resultados_file}")
    except Exception as e:
        print(f"Error guardando resultados: {e}")
      # Mostrar resumen comparativo
    print("\n" + "=" * 80)
    print("RESUMEN COMPARATIVO")
    print("=" * 80)
    
    # Tabla principal con métricas básicas
    formato = "{:<10} | {:<10} | {:<15} | {:<15} | {:<15}"
    print(formato.format("PIPELINE", "ESTADO", "TIEMPO (s)", "OFERTAS FILTRADAS", "OFERTAS TOTALES"))
    print("-" * 80)
    
    for nombre, resultado in resultados["resultados"].items():
        estado = resultado.get("estado", "?")
        tiempo = resultado.get("tiempo_segundos", 0)
        ofertas_filtradas = resultado.get("ofertas_filtradas", "?")
        ofertas_totales = resultado.get("ofertas_totales", "?")
        
        print(formato.format(
            nombre,
            estado,
            f"{tiempo:.2f}",
            str(ofertas_filtradas),
            str(ofertas_totales)
        ))
    
    # Mostrar tabla de fuentes (si está disponible)
    print("\n" + "-" * 80)
    print("FUENTES PROCESADAS")
    print("-" * 80)
    formato_fuentes = "{:<10} | {:<15} | {:<15}"
    print(formato_fuentes.format("PIPELINE", "FUENTES EXITOSAS", "FUENTES FALLIDAS"))
    print("-" * 80)
    
    for nombre, resultado in resultados["resultados"].items():
        fuentes_exitosas = resultado.get("fuentes_exitosas", "?")
        fuentes_fallidas = resultado.get("fuentes_fallidas", "?")
        
        print(formato_fuentes.format(
            nombre,
            str(fuentes_exitosas),
            str(fuentes_fallidas)
        ))
    
    # Mostrar métricas de mejora (comparando versiones)
    if "super" in resultados["resultados"] and "original" in resultados["resultados"]:
        super_result = resultados["resultados"]["super"]
        original_result = resultados["resultados"]["original"]
        
        print("\n" + "-" * 80)
        print("ANÁLISIS DE MEJORA (Super vs Original)")
        print("-" * 80)
        
        # Calcular porcentajes de mejora
        try:
            tiempo_original = original_result.get("tiempo_segundos", 0)
            tiempo_super = super_result.get("tiempo_segundos", 0)
            
            ofertas_original = original_result.get("ofertas_totales", 0)
            ofertas_super = super_result.get("ofertas_totales", 0)
            
            if isinstance(ofertas_original, str): ofertas_original = 0
            if isinstance(ofertas_super, str): ofertas_super = 0
            
            # Evitar división por cero
            if tiempo_original > 0:
                mejora_tiempo = ((tiempo_original - tiempo_super) / tiempo_original) * 100
                print(f"Mejora en tiempo: {mejora_tiempo:.1f}% ({'más rápido' if mejora_tiempo > 0 else 'más lento'})")
            
            if ofertas_original > 0:
                mejora_ofertas = ((ofertas_super - ofertas_original) / ofertas_original) * 100
                print(f"Mejora en ofertas encontradas: {mejora_ofertas:.1f}% ({'más ofertas' if mejora_ofertas > 0 else 'menos ofertas'})")
        except Exception as e:
            print(f"No se pudo calcular métricas de mejora: {e}")
    
    # Mostrar información sobre módulos mejorados disponibles
    if "super" in resultados["resultados"] and "modulos_mejorados" in resultados["resultados"]["super"]:
        modulos = resultados["resultados"]["super"]["modulos_mejorados"]
        if modulos:
            print("\n" + "-" * 80)
            print("MÓDULOS MEJORADOS DISPONIBLES")
            print("-" * 80)
            
            for modulo, disponible in modulos.items():
                print(f"{modulo}: {'✅ Activo' if disponible else '❌ No disponible'}")
    
    print("=" * 80)
    print("\nTest comparativo finalizado.")

if __name__ == "__main__":
    run_test_comparativo()
