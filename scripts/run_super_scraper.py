# -*- coding: utf-8 -*-
# /scripts/run_super_scraper.py

"""
Script para ejecutar y comparar las diferentes versiones del 
buscador de empleo inteligente.

Este script ejecuta los tres niveles de implementación para comparar resultados:
1. Pipeline original (main.py)
2. Pipeline mejorado (main_improved.py)
3. Super Pipeline (super_pipeline.py - todas las mejoras)

Compara tiempo de ejecución, cantidad de ofertas encontradas, y fuentes exitosas.
"""

import os
import sys
import time
import logging
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple
import importlib
import traceback

# Asegurar que podamos importar desde el directorio raíz
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Verificar disponibilidad de los módulos
def check_module_available(module_path: str) -> bool:
    """Verifica si un módulo está disponible"""
    try:
        # Intentar importar directamente en lugar de usar find_spec
        __import__(module_path)
        return True
    except (ImportError, ModuleNotFoundError):
        return False

# Configurar colores para la salida (ANSI)
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    """Imprime un encabezado formateado"""
    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(80)}{Colors.ENDC}")
    print("=" * 80)

def print_section(text):
    """Imprime un título de sección formateado"""
    print("\n" + "-" * 80)
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.ENDC}")
    print("-" * 80)

def print_result(label, value, success=True, is_improvement=False):
    """Imprime un resultado formateado con colores"""
    color = Colors.GREEN if success else Colors.RED
    improvement = ""
    if is_improvement and value is not None and isinstance(value, (int, float)):
        improvement = f" ({Colors.YELLOW}+{value}{Colors.ENDC})"
    
    print(f"{Colors.BOLD}{label}:{Colors.ENDC} {color}{value}{Colors.ENDC}{improvement}")

def calculate_improvement(new_value, original_value):
    """Calcula el porcentaje de mejora entre dos valores"""
    if original_value == 0:
        return 0.0 if new_value == 0 else 100.0
    
    improvement = ((new_value - original_value) / original_value) * 100
    return improvement

def run_pipeline(name, pipeline_func, results_dict, previous_result=None):
    """Ejecuta un pipeline y registra sus resultados"""
    print_section(f"Ejecutando {name}")
    
    start_time = time.time()
    try:
        result = pipeline_func()
        elapsed_time = time.time() - start_time
        
        if isinstance(result, dict):
            # Extraer métricas relevantes
            ofertas_raw = result.get('raw_jobs', 0)
            ofertas_procesadas = result.get('processed_jobs', 0)
            ofertas_filtradas = result.get('filtered_jobs', 0)
            fuentes_exitosas = result.get('successful_sources', 0)
            fuentes_fallidas = result.get('failed_sources', 0)
            
            # Mostrar resultados
            print(f"\n✅ {name} completado en {elapsed_time:.2f} segundos")
            print_result("Ofertas encontradas (sin procesar)", ofertas_raw)
            print_result("Ofertas procesadas", ofertas_procesadas)
            print_result("Ofertas filtradas", ofertas_filtradas)
            print_result("Fuentes exitosas", fuentes_exitosas)
            print_result("Fuentes fallidas", fuentes_fallidas)
            
            # Calcular mejoras si hay resultados previos
            if previous_result:
                print_section(f"Comparación con {previous_result['name']}")
                
                # Calcular mejoras
                tiempo_mejora = previous_result['time'] - elapsed_time
                ofertas_raw_mejora = calculate_improvement(ofertas_raw, previous_result['raw_jobs'])
                ofertas_filtradas_mejora = calculate_improvement(ofertas_filtradas, previous_result['filtered_jobs'])
                fuentes_exitosas_mejora = calculate_improvement(fuentes_exitosas, previous_result['successful_sources'])
                
                # Mostrar comparación
                tiempo_mejor = tiempo_mejora > 0
                print_result("Diferencia en tiempo", f"{abs(tiempo_mejora):.2f} segundos {'más rápido' if tiempo_mejor else 'más lento'}", tiempo_mejor)
                print_result("Mejora en ofertas encontradas", f"{ofertas_raw_mejora:.1f}%", ofertas_raw_mejora >= 0)
                print_result("Mejora en ofertas filtradas", f"{ofertas_filtradas_mejora:.1f}%", ofertas_filtradas_mejora >= 0)
                print_result("Mejora en fuentes exitosas", f"{fuentes_exitosas_mejora:.1f}%", fuentes_exitosas_mejora >= 0)
            
            # Guardar resultados
            results_dict[name] = {
                'name': name,
                'time': elapsed_time,
                'raw_jobs': ofertas_raw,
                'processed_jobs': ofertas_procesadas,
                'filtered_jobs': ofertas_filtradas,
                'successful_sources': fuentes_exitosas,
                'failed_sources': fuentes_fallidas,
                'success': True,
                'message': result.get('message', 'OK')
            }
            
        else:
            print(f"\n⚠️ {name} completado pero retornó un formato inesperado")
            results_dict[name] = {
                'name': name,
                'time': elapsed_time,
                'success': True,
                'message': "Formato de resultado inesperado"
            }
            
    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"\n❌ Error ejecutando {name}: {str(e)}")
        traceback.print_exc()
        
        results_dict[name] = {
            'name': name,
            'time': elapsed_time,
            'success': False,
            'error': str(e)
        }

def run_test_comparativo(params=None):
    """
    Ejecuta un test comparativo entre las diferentes versiones del pipeline
    
    Args:
        params: Parámetros de búsqueda opcionales
    """
    print_header("TEST COMPARATIVO DE BUSCADOR DE EMPLEO INTELIGENTE")
    print(f"\nFecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Verificar módulos disponibles
    print_section("Verificando módulos disponibles")
    
    modules = {
        'Pipeline Original': 'src.main',
        'Pipeline Mejorado': 'src.main_improved',
        'Super Pipeline': 'src.super_pipeline',
        'Cliente HTTP Mejorado': 'src.utils.http_client_improved',
        'Manejador de Errores': 'src.utils.error_handler',
        'LinkedIn Scraper Mejorado': 'src.scrapers.linkedin_scraper_improved',
        'InfoJobs Scraper Mejorado': 'src.scrapers.infojobs_scraper_improved',
        'Computrabajo Scraper Mejorado': 'src.scrapers.computrabajo_scraper_improved',
        'Adzuna Client Mejorado': 'src.apis.adzuna_client_improved'
    }
    
    modules_available = {}
    for name, module_path in modules.items():
        is_available = check_module_available(module_path)
        modules_available[name] = is_available
        status = f"{Colors.GREEN}✅ Disponible{Colors.ENDC}" if is_available else f"{Colors.RED}❌ No disponible{Colors.ENDC}"
        print(f"{name}: {status}")
    
    # Definir funciones para las pipelines disponibles
    pipelines = []
    
    if modules_available['Pipeline Original']:
        try:
            from src.main import run_job_search_pipeline as run_original
            pipelines.append(('Pipeline Original', run_original))
        except ImportError:
            print(f"{Colors.RED}❌ No se pudo importar Pipeline Original{Colors.ENDC}")
    
    if modules_available['Pipeline Mejorado']:
        try:
            from src.main_improved import run_job_search_pipeline as run_improved
            pipelines.append(('Pipeline Mejorado', run_improved))
        except ImportError:
            print(f"{Colors.RED}❌ No se pudo importar Pipeline Mejorado{Colors.ENDC}")
    
    if modules_available['Super Pipeline']:
        try:
            from src.super_pipeline import run_job_search_pipeline_super as run_super
            pipelines.append(('Super Pipeline', run_super))
        except ImportError:
            print(f"{Colors.RED}❌ No se pudo importar Super Pipeline{Colors.ENDC}")
    
    if not pipelines:
        print(f"{Colors.RED}❌ Error: No hay pipelines disponibles para ejecutar{Colors.ENDC}")
        return
    
    # Ejecutar pipelines
    results = {}
    previous_result = None
    
    for name, pipeline_func in pipelines:
        run_pipeline(name, pipeline_func, results, previous_result)
        previous_result = results.get(name)
        
        # Pequeña pausa entre pipelines para liberar recursos
        if pipelines.index((name, pipeline_func)) < len(pipelines) - 1:
            print("\nEsperando 5 segundos antes de ejecutar el siguiente pipeline...")
            time.sleep(5)
    
    # Guardar resultados
    results_dir = project_root / "test_results"
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"comparativo_{timestamp}.json"
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': timestamp,
            'modules_available': modules_available,
            'results': results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nResultados guardados en: {results_file}")
    
    # Mostrar tabla comparativa final
    print_section("RESUMEN COMPARATIVO")
    
    # Encabezados de tabla
    print(f"{'Pipeline':<20} | {'Tiempo (s)':<12} | {'Ofertas':<12} | {'Filtradas':<12} | {'Fuentes OK':<12}")
    print("-" * 80)
    
    for name in ['Pipeline Original', 'Pipeline Mejorado', 'Super Pipeline']:
        if name in results:
            result = results[name]
            tiempo = f"{result.get('time', 0):.2f}"
            ofertas = result.get('raw_jobs', 'N/A')
            filtradas = result.get('filtered_jobs', 'N/A')
            fuentes = result.get('successful_sources', 'N/A')
            
            # Estado (color según éxito)
            color = Colors.GREEN if result.get('success', False) else Colors.RED
            
            print(f"{name:<20} | {color}{tiempo:<12}{Colors.ENDC} | {color}{ofertas:<12}{Colors.ENDC} | {color}{filtradas:<12}{Colors.ENDC} | {color}{fuentes:<12}{Colors.ENDC}")
    
    print_header("FIN DEL TEST COMPARATIVO")

if __name__ == "__main__":
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Ejecuta un test comparativo entre versiones del buscador de empleo')
    parser.add_argument('--query', type=str, help='Consulta de búsqueda (opcional)')
    parser.add_argument('--location', type=str, help='Ubicación de búsqueda (opcional)')
    
    args = parser.parse_args()
    
    # Ejecutar test con los parámetros proporcionados (si los hay)
    params = {}
    if args.query:
        params['query'] = args.query
    if args.location:
        params['location'] = args.location
        
    run_test_comparativo(params if params else None)
