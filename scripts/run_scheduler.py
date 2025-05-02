# -*- coding: utf-8 -*-
# /scripts/run_scheduler.py

"""
Script para Iniciar el Programador de Tareas (Scheduler).

Este script importa y ejecuta la función 'start_scheduler' del módulo
'src.scheduler.job_scheduler', la cual contiene el bucle principal
que ejecuta el pipeline de búsqueda de empleo periódicamente según
el horario definido.

Uso:
    python scripts/run_scheduler.py [--run-now]

Argumentos opcionales:
  --run-now   Ejecuta el pipeline de búsqueda una vez inmediatamente
              al inicio, además de programarlo para el futuro.

Nota:
  Este script está diseñado para correr de forma continua (en un bucle infinito).
  Deberás ejecutarlo en segundo plano usando herramientas como 'nohup',
  'screen', 'tmux', o un gestor de procesos como 'systemd' o 'supervisor'
  si quieres que siga funcionando después de cerrar tu terminal.
"""

import sys
import argparse # Para manejar argumentos de línea de comandos como --run-now
import logging
from pathlib import Path
import time # Podríamos necesitarlo si hay errores de importación

# --- Asegurar que podamos importar desde 'src' ---
# Añadimos la carpeta raíz del proyecto (un nivel arriba de 'scripts') al PYTHONPATH
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
print(f"INFO: Añadido al PYTHONPATH: {project_root}") # Para depuración de imports

# --- Importar la función clave del scheduler ---
try:
    from src.scheduler.job_scheduler import start_scheduler
    # También importamos el setup de logging por si falla antes de que start_scheduler lo haga
    from src.utils import logging_config
except ImportError as e:
    print(f"ERROR CRÍTICO: No se pudieron importar módulos necesarios (start_scheduler o logging_config): {e}", file=sys.stderr)
    print("Verifica que la estructura del proyecto sea correcta y que te encuentras en la carpeta raíz.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
     print(f"ERROR CRÍTICO inesperado durante la importación: {e}", file=sys.stderr)
     sys.exit(1)

# Configurar un logger básico aquí por si setup_logging falla
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger("run_scheduler_script")


def main():
    """Función principal que parsea argumentos y lanza el scheduler."""

    # Configuramos para poder pasarle un argumento opcional --run-now
    parser = argparse.ArgumentParser(
        description='Lanza el programador de búsqueda de empleos.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--run-now',
        action='store_true', # Si aparece el flag, args.run_now será True
        help='Ejecuta el pipeline una vez inmediatamente antes de iniciar el schedule.'
    )
    args = parser.parse_args()

    logger.info(f"Lanzando el scheduler desde {__file__}...")
    if args.run_now:
        logger.info("Opción --run-now detectada: Se ejecutará la tarea una vez al inicio.")

    try:
        # ¡Llamamos a la función que contiene el bucle infinito del scheduler!
        # Le pasamos el valor del flag --run-now.
        start_scheduler(run_immediately=args.run_now)
        # Si start_scheduler termina (por ejemplo, por un Ctrl+C), lo indicamos.
        logger.info("El scheduler ha terminado.")

    except ImportError:
         # Esto no debería pasar si las importaciones iniciales funcionaron, pero por si acaso.
         logger.critical("Parece que hubo un problema al importar los módulos necesarios dentro de start_scheduler.")
    except KeyboardInterrupt:
         logger.info("Script run_scheduler interrumpido por el usuario (Ctrl+C).")
    except Exception as e:
        logger.critical("¡ERROR FATAL! El scheduler falló inesperadamente.", exc_info=True)


# Punto de entrada del script
if __name__ == "__main__":
    main()