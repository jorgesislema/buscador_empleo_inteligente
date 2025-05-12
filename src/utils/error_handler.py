# -*- coding: utf-8 -*-
# /src/utils/error_handler.py

"""
Módulo para el manejo mejorado de errores en el buscador de empleo.

Proporciona funciones y decoradores para manejar errores comunes en las peticiones HTTP,
almacenar información sobre errores para análisis posterior, y garantizar que los fallos
en scrapers individuales no detengan todo el proceso de búsqueda.
"""

import logging
import functools
import traceback
import time
import ssl
import requests
from typing import Dict, Any, Callable, List, Optional, TypeVar, Union

# Type variables para el decorador
T = TypeVar('T')
R = TypeVar('R')

logger = logging.getLogger(__name__)

# Registro de errores para análisis posterior
error_registry = {
    'ssl_errors': [],
    'http_errors': [],
    'timeout_errors': [],
    'connection_errors': [],
    'parser_errors': [],
    'other_errors': []
}

def clear_error_registry():
    """Limpia el registro de errores."""
    for key in error_registry:
        error_registry[key] = []

def get_error_summary() -> Dict[str, int]:
    """
    Retorna un resumen de los errores registrados.
    
    Returns:
        Dict[str, int]: Conteo de errores por categoría
    """
    return {key: len(values) for key, values in error_registry.items()}

def register_error(error_type: str, source_name: str, error_details: str, url: Optional[str] = None):
    """
    Registra un error para análisis posterior.
    
    Args:
        error_type: Tipo de error (ssl, http, timeout, connection, parser, other)
        source_name: Nombre de la fuente que generó el error
        error_details: Detalles del error
        url: URL que causó el error (opcional)
    """
    if error_type not in error_registry:
        error_type = 'other_errors'
    
    error_entry = {
        'source': source_name,
        'details': error_details,
        'timestamp': time.time(),
        'url': url
    }
    
    error_registry[error_type].append(error_entry)
    logger.debug(f"Error registrado para análisis: {error_type} en {source_name}")

def safe_request_handler(func: Callable[..., T]) -> Callable[..., Optional[T]]:
    """
    Decorador para manejar de forma segura las peticiones HTTP y otros errores comunes.
    
    Args:
        func: Función a decorar, generalmente métodos de scrapers o clientes API
        
    Returns:
        Wrapper que maneja los errores comunes y registra información útil
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Intentamos obtener el nombre de la fuente del primer argumento (self)
        source_name = getattr(args[0], 'source_name', 'unknown_source') if args else 'unknown_source'
        
        try:
            return func(*args, **kwargs)
        except ssl.SSLError as e:
            error_msg = f"Error SSL en {source_name}: {str(e)}"
            logger.error(error_msg)
            register_error('ssl_errors', source_name, str(e))
            # Podríamos intentar desactivar la verificación SSL como último recurso
            # if 'verify' in kwargs and kwargs['verify']:
            #     logger.warning(f"Reintentando sin verificación SSL para {source_name}")
            #     kwargs['verify'] = False
            #     return func(*args, **kwargs)
            return None
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if hasattr(e, 'response') else 'desconocido'
            error_msg = f"Error HTTP {status_code} en {source_name}: {str(e)}"
            logger.error(error_msg)
            url = e.response.url if hasattr(e, 'response') else None
            register_error('http_errors', source_name, f"{status_code}: {str(e)}", url)
            return None
        except requests.exceptions.Timeout as e:
            error_msg = f"Timeout en {source_name}: {str(e)}"
            logger.error(error_msg)
            register_error('timeout_errors', source_name, str(e))
            return None
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Error de conexión en {source_name}: {str(e)}"
            logger.error(error_msg)
            register_error('connection_errors', source_name, str(e))
            return None
        except Exception as e:
            error_msg = f"Error inesperado en {source_name}: {str(e)}"
            logger.exception(error_msg)
            register_error('other_errors', source_name, f"{type(e).__name__}: {str(e)}")
            return None
    
    return wrapper

def retry_on_failure(max_retries: int = 3, backoff_factor: float = 0.5) -> Callable:
    """
    Decorador para reintentar una función cuando falla, con espera exponencial.
    
    Args:
        max_retries: Número máximo de reintentos
        backoff_factor: Factor de espera entre reintentos
        
    Returns:
        Decorador que reintenta la función en caso de error
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Optional[T]]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Intentamos obtener el nombre de la fuente del primer argumento (self)
            source_name = getattr(args[0], 'source_name', 'unknown_source') if args else 'unknown_source'
            
            last_exception = None
            for attempt in range(max_retries + 1):  # +1 porque el primer intento no es reintento
                try:
                    if attempt > 0:
                        # Calculamos el tiempo de espera exponencial
                        wait_time = backoff_factor * (2 ** (attempt - 1))
                        logger.info(f"Reintento {attempt}/{max_retries} para {source_name} en {wait_time:.2f} segundos...")
                        time.sleep(wait_time)
                    
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_type = type(e).__name__
                    if attempt < max_retries:
                        logger.warning(f"Intento {attempt+1}/{max_retries+1} falló para {source_name}: {error_type} - {str(e)}")
                    else:
                        logger.error(f"Todos los reintentos fallaron para {source_name}: {error_type} - {str(e)}")
            
            # Si llegamos aquí, todos los intentos fallaron
            if last_exception:
                logger.exception(f"Error final después de {max_retries+1} intentos para {source_name}", exc_info=last_exception)
            
            return None
        
        return wrapper
    
    return decorator

def make_search_more_robust(search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Genera variaciones más robustas de los parámetros de búsqueda.
    
    Crea combinaciones más simples y específicas para aumentar las 
    probabilidades de obtener resultados cuando las búsquedas fallan.
    
    Args:
        search_params: Parámetros de búsqueda originales
        
    Returns:
        Lista de variaciones de parámetros de búsqueda
    """
    variations = [search_params.copy()]  # Incluimos los parámetros originales
    
    # Obtenemos las keywords originales
    keywords = search_params.get('keywords', [])
    location = search_params.get('location', None)
    
    # Si hay muchas keywords, creamos versiones con menos keywords
    if keywords and len(keywords) > 5:
        # Versión con solo las primeras 3 keywords principales
        variations.append({
            'keywords': keywords[:3],
            'location': location
        })
        
        # Versión con keywords más técnicas (si hay más de 10)
        if len(keywords) > 10:
            # Algunas keywords técnicas comunes que suelen dar buenos resultados
            tech_keywords = [k for k in keywords if k.lower() in 
                            ['python', 'javascript', 'react', 'data', 'developer', 
                             'programador', 'software', 'web', 'frontend', 'backend']]
            if tech_keywords:
                variations.append({
                    'keywords': tech_keywords[:5],  # Solo las primeras 5 tech keywords
                    'location': location
                })
    
    # Versión sin ubicación si hay keywords
    if keywords:
        variations.append({
            'keywords': keywords[:5] if len(keywords) > 5 else keywords,
            'location': None
        })
    
    # Versión con términos genéricos de tecnología si todo lo demás falla
    variations.append({
        'keywords': ['software', 'developer', 'programador', 'web', 'data'],
        'location': location
    })
    
    return variations
