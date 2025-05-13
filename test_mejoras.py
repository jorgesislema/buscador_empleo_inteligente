#!/usr/bin/env python
# -*- coding: utf-8 -*-
# test_mejoras.py

"""
Script para probar las mejoras implementadas en el buscador de empleo inteligente.
Este script ejecuta y compara el pipeline original, el mejorado y el super pipeline
para verificar que las mejoras aumentan el número de fuentes exitosas y ofertas encontradas.
"""

import os
import sys
import time
import json
import importlib.util
from datetime import datetime
from pathlib import Path

# Asegurar que podamos importar desde el directorio raíz
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_module_exists(module_path):
    """Verifica si un módulo existe en el sistema."""
    try:
        # Intentar importar directamente en lugar de usar find_spec
        __import__(module_path)
        return True
    except ImportError:
        return False

def print_header(text):
    """Imprime un encabezado formateado."""
    print("\n" + "=" * 80)
    print(f" {text} ".center(80, "="))
    print("=" * 80)

def print_section(text):
    """Imprime un encabezado de sección."""
    print("\n" + "-" * 80)
    print(f" {text} ".center(80, "-"))
    print("-" * 80)

def run_test():
    print_header("TEST DE MEJORAS PARA EL BUSCADOR DE EMPLEO INTELIGENTE")
    print(f"Fecha de ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Crear directorio para resultados de prueba si no existe
    results_dir = project_root / "test_results"
    results_dir.mkdir(exist_ok=True)
    
    # Timestamp para los archivos de resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Verificar disponibilidad de módulos mejorados
    print_section("VERIFICACIÓN DE MÓDULOS MEJORADOS")
    
    modules_to_check = [
        ('src.utils.http_client_improved', "Cliente HTTP Mejorado"),
        ('src.utils.error_handler', "Manejador de Errores"),
        ('src.scrapers.linkedin_scraper_improved', "LinkedIn Scraper Mejorado"),
        ('src.scrapers.infojobs_scraper_improved', "InfoJobs Scraper Mejorado"),
        ('src.scrapers.computrabajo_scraper_improved', "Computrabajo Scraper Mejorado"),
        ('src.apis.adzuna_client_improved', "Adzuna Client Mejorado"),
        ('src.super_pipeline', "Super Pipeline")
    ]
    
    modules_available = {}
    for module_path, description in modules_to_check:
        is_available = check_module_exists(module_path)
        modules_available[module_path] = is_available
        status = "✅ Disponible" if is_available else "❌ No disponible"
        print(f"{description}: {status}")
    
    print_section("EJECUCIÓN DE PIPELINES")
    
    # Preparar registro de resultados
    test_results = {
        "fecha": datetime.now().isoformat(),
        "modulos_disponibles": modules_available,
        "pipelines": {}
    }
    
    # Ejecutar pipeline original
    print("\n1. Ejecutando pipeline original...")
    start_original = time.time()
    try:
        from src.main import run_job_search_pipeline as original_pipeline
        original_result = original_pipeline()
        time_original = time.time() - start_original
        print(f"   ✅ Completado en {time_original:.2f} segundos.")
        
        if isinstance(original_result, dict):
            ofertas_originales = original_result.get("processed_jobs", 0)
            print(f"   📊 Ofertas encontradas: {ofertas_originales}")
            
            test_results["pipelines"]["original"] = {
                "tiempo": time_original,
                "ofertas": ofertas_originales,
                "exito": True,
                "mensaje": original_result.get("message", "OK")
            }
        else:
            print("   ⚠️ Resultado no es un diccionario. No se pueden extraer estadísticas.")
            test_results["pipelines"]["original"] = {
                "tiempo": time_original,
                "exito": True,
                "mensaje": "Resultado con formato inesperado"
            }
    except Exception as e:
        print(f"   ❌ Error ejecutando pipeline original: {str(e)}")
        test_results["pipelines"]["original"] = {
            "tiempo": time.time() - start_original,
            "exito": False,
            "error": str(e)
        }
    
    # Breve pausa para asegurar que los recursos se liberan
    time.sleep(2)
    
    # Ejecutar pipeline mejorado
    print("\n2. Ejecutando pipeline mejorado...")
    start_improved = time.time()
    try:
        from src.main_improved import run_job_search_pipeline as improved_pipeline
        improved_result = improved_pipeline()
        time_improved = time.time() - start_improved
        print(f"   ✅ Completado en {time_improved:.2f} segundos.")
        
        if isinstance(improved_result, dict):
            ofertas_mejoradas = improved_result.get("processed_jobs", 0)
            print(f"   📊 Ofertas encontradas: {ofertas_mejoradas}")
            
            test_results["pipelines"]["mejorado"] = {
                "tiempo": time_improved,
                "ofertas": ofertas_mejoradas,
                "exito": True,
                "mensaje": improved_result.get("message", "OK")
            }
        else:
            print("   ⚠️ Resultado no es un diccionario. No se pueden extraer estadísticas.")
            test_results["pipelines"]["mejorado"] = {
                "tiempo": time_improved,
                "exito": True,
                "mensaje": "Resultado con formato inesperado"
            }
    except Exception as e:
        print(f"   ❌ Error ejecutando pipeline mejorado: {str(e)}")
        test_results["pipelines"]["mejorado"] = {
            "tiempo": time.time() - start_improved,
            "exito": False,
            "error": str(e)
        }
    
    # Breve pausa para asegurar que los recursos se liberan
    time.sleep(2)
    
    # Ejecutar super pipeline si está disponible
    if modules_available.get('src.super_pipeline', False):
        print("\n3. Ejecutando super pipeline...")
        start_super = time.time()
        try:
            from src.super_pipeline import run_job_search_pipeline_super as super_pipeline
            super_result = super_pipeline()
            time_super = time.time() - start_super
            print(f"   ✅ Completado en {time_super:.2f} segundos.")
            
            if isinstance(super_result, dict):
                ofertas_super = super_result.get("filtered_jobs", 0)
                print(f"   📊 Ofertas encontradas: {ofertas_super}")
                
                test_results["pipelines"]["super"] = {
                    "tiempo": time_super,
                    "ofertas": ofertas_super,
                    "exito": True,
                    "mensaje": super_result.get("message", "OK")
                }
            else:
                print("   ⚠️ Resultado no es un diccionario. No se pueden extraer estadísticas.")
                test_results["pipelines"]["super"] = {
                    "tiempo": time_super,
                    "exito": True,
                    "mensaje": "Resultado con formato inesperado"
                }
        except Exception as e:
            print(f"   ❌ Error ejecutando super pipeline: {str(e)}")
            test_results["pipelines"]["super"] = {
                "tiempo": time.time() - start_super,
                "exito": False,
                "error": str(e)
            }
    else:
        print("\n3. Super pipeline no disponible, saltando prueba.")
    
    # Guardar resultados en JSON
    results_file = results_dir / f"test_results_{timestamp}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(test_results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResultados guardados en: {results_file}")
    
    # Imprimir resumen comparativo
    print_section("RESUMEN COMPARATIVO")
    
    pipelines = ["original", "mejorado", "super"]
    print(f"{'Pipeline':<10} | {'Tiempo (s)':<12} | {'Ofertas':<10} | {'Estado':<10}")
    print("-" * 50)
    
    for pipeline in pipelines:
        if pipeline in test_results["pipelines"]:
            result = test_results["pipelines"][pipeline]
            tiempo = f"{result.get('tiempo', 0):.2f}"
            ofertas = result.get('ofertas', "N/A")
            estado = "✅ Éxito" if result.get('exito', False) else "❌ Error"
            
            print(f"{pipeline:<10} | {tiempo:<12} | {ofertas:<10} | {estado:<10}")
    
    print_header("FIN DEL TEST")

if __name__ == "__main__":
    run_test()
    
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
