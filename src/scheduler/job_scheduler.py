# -*- coding: utf-8 -*-
# /src/scheduler/job_scheduler.py

"""
Módulo Programador de Tareas (Job Scheduler).

Utiliza la librería 'schedule' para ejecutar periódicamente el pipeline
principal de búsqueda de empleo definido en 'src.main'.

¡Este es el piloto automático de nuestro buscador! 🚀
"""

import schedule # La librería para programar tareas. ¡Añadir a requirements.txt!
import time     # Para pausar entre verificaciones de schedule.
import logging
from typing import Callable # Para type hints de funciones
import sys
from pathlib import Path

# Añadimos la raíz del proyecto para importar 'src'
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Importamos nuestras utilidades y (¡importante!) la función principal de main
try:
    from src.utils import logging_config
    # --- ¡ASUNCIÓN IMPORTANTE! ---
    # Asumimos que en 'src/main.py' existirá una función llamada 'run_job_search_pipeline'
    # que se encargará de ejecutar todo el flujo (llamar scrapers/apis, filtrar, guardar).
    # Si la llamas diferente en main.py, ¡hay que cambiar este import!
    from src.main import run_job_search_pipeline # except ImportError as e:
    print(f"Error: No se pudo importar 'run_job_search_pipeline' desde 'src.main' o 'logging_config'. {e}")
    print("Asegúrate de que 'src/main.py' exista y contenga esa función, y que el logging esté configurado.")
    print("Este scheduler no funcionará sin la función principal a ejecutar.")
    # Salimos si no podemos importar lo esencial.
    sys.exit(1)
except ModuleNotFoundError:
     # Esto puede pasar si src.main aún no existe.
     print("ERROR: El módulo 'src.main' parece no existir aún. Crea 'src/main.py' con la función 'run_job_search_pipeline'.")
     # Definimos una función dummy para que el resto del script no falle al cargar,
     # pero no hará nada útil.
     def run_job_search_pipeline():
         print("ERROR: run_job_search_pipeline (de src/main.py) no está disponible!")
         pass # No hacer nada.
     # Configuración básica de logging en este caso
     logging.basicConfig(level=logging.INFO)


# Logger para el scheduler
logger = logging.getLogger(__name__)

# --- Tarea a Ejecutar ---

def _run_scheduled_job():
    """
    Función que será llamada por el scheduler. Ejecuta el pipeline principal.
    Incluye manejo de errores para que el scheduler no se detenga si falla una ejecución.
    """
    logger.info("====== INICIANDO EJECUCIÓN PROGRAMADA DEL PIPELINE ======")
    try:
        # ¡Aquí llamamos a la función principal de nuestro main.py!
        run_job_search_pipeline()
        logger.info("====== PIPELINE DE BÚSQUEDA EJECUTADO EXITOSAMENTE ======")
    except Exception as e:
        # ¡Atrapamos cualquier error para que no rompa el bucle del scheduler!
        logger.exception("====== ¡ERROR DURANTE LA EJECUCIÓN PROGRAMADA DEL PIPELINE! ======")
        # Podríamos añadir notificaciones aquí (email, Slack, etc.) si quisiéramos.
    finally:
        # Este bloque se ejecuta siempre, haya habido error o no.
        # Mostramos la próxima vez que se ejecutará la tarea.
        try:
             next_run_time = schedule.next_run
             if next_run_time:
                 logger.info(f"Próxima ejecución programada para: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
             else:
                 logger.info("No hay más ejecuciones programadas (esto no debería pasar en el bucle principal).")
        except Exception as e:
            logger.error(f"Error obteniendo la próxima hora de ejecución: {e}")
        logger.info("====== FIN DE LA EJECUCIÓN PROGRAMADA ======")


# --- Función Principal del Scheduler ---

def start_scheduler(run_immediately: bool = False):
    """
    Configura el horario y arranca el bucle infinito del programador.

    Args:
        run_immediately (bool): Si es True, ejecuta la tarea una vez
                                al iniciar, además de programarla.
                                Defaults to False.
    """
    # Nos aseguramos de que el logging esté configurado antes de empezar.
    try:
        logging_config.setup_logging()
    except Exception as e:
         logger.error(f"Error configurando el logging en start_scheduler: {e}")
         # Continuar sin configuración avanzada puede ser problemático, pero intentamos.

    logger.info("***** Iniciando el Job Scheduler *****")

    # --- Definir el Horario ---
    # ¡Aquí es donde decimos cuándo queremos que se ejecute!
    # Ejemplos:
    # schedule.every().day.at("03:00").do(_run_scheduled_job) # Todos los días a las 3:00 AM
    # schedule.every().hour.do(_run_scheduled_job)          # Cada hora
    # schedule.every(6).hours.do(_run_scheduled_job)        # Cada 6 horas
    # schedule.every().monday.at("09:00").do(_run_scheduled_job) # Los lunes a las 9 AM

    # Usemos una opción común: todos los días a una hora de baja actividad.
    # ¡OJO! La hora es la del servidor donde corra el script.
    schedule_time = "03:00" # schedule.every().day.at(schedule_time).do(_run_scheduled_job)
    logger.info(f"Pipeline de búsqueda programado para ejecutarse todos los días a las {schedule_time}.")

    # Si queremos ejecutarlo una vez al arrancar (útil para probar)
    if run_immediately:
        logger.info("Ejecutando la tarea una vez inmediatamente al inicio...")
        _run_scheduled_job() # Lo llamamos directamente una vez.

    # Mostramos la primera ejecución programada.
    try:
        first_run = schedule.next_run
        if first_run:
            logger.info(f"Primera ejecución programada para: {first_run.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
         logger.error(f"Error obteniendo la primera hora de ejecución: {e}")

    # --- Bucle Infinito del Scheduler ---
    # Este bucle mantiene el script vivo, revisando si hay tareas pendientes.
    logger.info("Entrando en el bucle principal del scheduler (Ctrl+C para salir)...")
    while True:
        try:
            # Comprueba si hay alguna tarea pendiente de ejecutar según el horario.
            schedule.run_pending()
            # Esperamos un tiempo antes de volver a comprobar. No necesita ser súper preciso.
            # Esperar 60 segundos es razonable para tareas diarias/horarias.
            time.sleep(60) # Dormir por 60 segundos.
        except KeyboardInterrupt:
             logger.info("Se recibió interrupción de teclado (Ctrl+C). Saliendo del scheduler.")
             break # Salir del bucle si presionamos Ctrl+C
        except Exception as e:
             # Capturar otros posibles errores en el propio bucle de schedule.
             logger.exception(f"Error inesperado en el bucle del scheduler: {e}")
             # Esperar un poco más antes de reintentar para no saturar en caso de error persistente.
             time.sleep(300) # Esperar 5 minutos


# --- Punto de Entrada (si quisiéramos ejecutar este archivo directamente) ---
if __name__ == "__main__":
    # Esto permite lanzar el scheduler directamente con: python src/scheduler/job_scheduler.py
    # Aunque es más limpio tener un script en /scripts/ para lanzarlo.
    print("Ejecutando el scheduler directamente...")
    # Podríamos añadir un argumento para el --run-immediately aquí si quisiéramos
    # start_scheduler(run_immediately=True) # Ejemplo para ejecutar ya
    start_scheduler(run_immediately=False)