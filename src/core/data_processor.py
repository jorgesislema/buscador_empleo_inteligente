# /src/core/data_processor.py

"""
Módulo de Procesamiento y Limpieza de Datos de Ofertas.

Este módulo toma la lista de ofertas recolectadas (posiblemente de
 diferentes fuentes con pequeñas inconsistencias) y aplica pasos de
 limpieza y estandarización básica ANTES de filtrarlas o guardarlas.

El objetivo es tener datos más consistentes y limpios.
"""

import logging
from typing import List, Dict, Any, Optional
import re
import html

logger = logging.getLogger(__name__)


def _clean_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    if not isinstance(text, str):
        logger.warning(f"Se esperaba str para limpiar, pero se recibió {type(text)}. Se devuelve como está.")
        return text
    try:
        text = html.unescape(text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text if text else None
    except Exception as e:
        logger.error(f"Error al limpiar texto: '{str(text)[:100]}...'. Error: {e}", exc_info=True)
        return text


def process_job_offers(job_offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not job_offers:
        logger.info("No hay ofertas para procesar.")
        return []

    logger.info(f"Procesando {len(job_offers)} ofertas...")
    processed_jobs = []

    for i, job in enumerate(job_offers):
        processed_job = job.copy()
        try:
            for key in ['titulo', 'empresa', 'ubicacion', 'descripcion', 'salario']:
                if key in processed_job:
                    processed_job[key] = _clean_text(processed_job.get(key))
            processed_jobs.append(processed_job)
        except Exception as e:
            logger.error(f"Error al procesar oferta {i} ({job.get('url', 'sin URL')}): {e}", exc_info=True)

    logger.info(f"{len(processed_jobs)} ofertas procesadas correctamente.")
    return processed_jobs


if __name__ == '__main__':
    import pprint
    logging.basicConfig(level=logging.DEBUG)

    ofertas_sucias = [
        {
            'titulo': '  Analista de Datos Senior   ',
            'empresa': 'Empresa &amp; Co. ',
            'ubicacion': '  Remoto (LATAM)  \n ',
            'descripcion': '   Buscamos experto en <b>SQL</b>.\n\n   Conocimientos de    Python. ',
            'fecha_publicacion': '2025-05-01',
            'url': 'http://ejemplo.com/1',
            'fuente': 'Test',
            'salario': '  USD 50k - 70k Anual  '
        },
        {
            'titulo': 'Data Engineer',
            'empresa': None,
            'ubicacion': 'Quito',
            'descripcion': '<p>ETL y Cloud.</p> Tareas:<br>- Pipeline<br>- Optimización',
            'fecha_publicacion': 'hace 5 días',
            'url': 'http://ejemplo.com/2',
            'fuente': 'Test2',
            'salario': None
        },
        {
            'titulo': 12345,
            'empresa': 'Otra Corp',
            'ubicacion': 'Remoto',
            'descripcion': 'Descripción válida.',
            'fecha_publicacion': '2025-05-03',
            'url': 'http://ejemplo.com/3',
            'fuente': 'Test3'
        }
    ]

    print("\n--- Ofertas Originales ---")
    pprint.pprint(ofertas_sucias)

    ofertas_limpias = process_job_offers(ofertas_sucias)

    print("\n--- Ofertas Procesadas ---")
    pprint.pprint(ofertas_limpias)
