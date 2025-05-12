# -*- coding: utf-8 -*-
# /src/utils/http_client_improved.py

"""
Cliente HTTP Mejorado para el Buscador de Empleo.

Versión mejorada del HTTPClient que incluye:
- Mejor manejo de errores SSL
- Reintentos más inteligentes
- Modo de compatibilidad para sitios problemáticos
- Detección y solución automática de problemas comunes
- Rotación de User Agents y proxies (opcional)
"""

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import urllib3
import ssl
import time
import logging
import random
import json
from typing import Optional, Dict, Any, Tuple, List, Union

# Deshabilitamos las advertencias de SSL inseguro en modo debug
# Esto NO afecta a la verificación SSL que seguirá activada por defecto
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# --- Constantes y Configuraciones por Defecto ---
DEFAULT_USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                     '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')

DEFAULT_TIMEOUT = (15, 45)  # (timeout conexión, timeout lectura)

DEFAULT_DELAY_SECONDS = 1.5
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 0.8 
STATUS_CODES_TO_RETRY = [429, 500, 502, 503, 504]

# Lista de User-Agents modernos para rotación
USER_AGENTS = [
    # Chrome en Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    # Firefox en Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    # Edge en Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.2277.128',
    # Safari en macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    # Chrome en macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    # Firefox en macOS
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0',
    # Chrome en Linux
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    # Firefox en Linux
    'Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0',
    # Android Chrome
    'Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36',
    # iOS Safari
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'
]

class SSLContextAdapter(HTTPAdapter):
    """
    Adaptador personalizado que permite usar diferentes contextos SSL para sitios problemáticos.
    Esto permite que el cliente sea más flexible con sitios que tienen configuraciones SSL obsoletas.
    """
    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super(SSLContextAdapter, self).__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        if self.ssl_context:
            kwargs['ssl_context'] = self.ssl_context
        return super(SSLContextAdapter, self).init_poolmanager(*args, **kwargs)

class ImprovedHTTPClient:
    """
    Cliente HTTP mejorado con manejo inteligente de errores y mayor compatibilidad.
    """
    def __init__(self, user_agent=DEFAULT_USER_AGENT, timeout=DEFAULT_TIMEOUT,
                retries=DEFAULT_RETRIES, backoff_factor=DEFAULT_BACKOFF_FACTOR,
                status_forcelist=STATUS_CODES_TO_RETRY):
        """
        Inicializa el cliente HTTP mejorado.
        """
        logger.info("Inicializando ImprovedHTTPClient con manejo inteligente de errores...")
        
        # Sesión principal con verificación SSL normal
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': user_agent})
        
        # Sesión alternativa para sitios con problemas de SSL (último recurso)
        self.fallback_session = requests.Session()
        self.fallback_session.headers.update({'User-Agent': user_agent})
        
        # Añadimos headers más realistas para ambas sesiones
        self._add_realistic_headers(self.session)
        self._add_realistic_headers(self.fallback_session)
        
        # Configurar User Agents
        self.user_agents = USER_AGENTS
        
        # Guardamos los timeouts
        self.default_timeout = timeout
        
        # Configuración de reintentos para la sesión principal
        self._setup_retry_strategy(self.session, retries, status_forcelist, backoff_factor)
        
        # Configuración de la sesión de fallback para sitios problemáticos
        self._setup_fallback_session()
        
        # Contador de intentos fallidos por dominio
        self.domain_failures = {}
        
        # Estadísticas
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'retries': 0,
            'fallback_used': 0,
            'ssl_errors': 0,
            'http_errors': 0,
            'connection_errors': 0
        }
    
    def _add_realistic_headers(self, session):
        """Añade headers realistas para simular un navegador moderno."""
        additional_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
        session.headers.update(additional_headers)
        logger.debug(f"Headers configurados para simular navegador moderno")
    
    def _setup_retry_strategy(self, session, retries, status_forcelist, backoff_factor):
        """Configura la estrategia de reintentos para una sesión."""
        try:
            retry_strategy = Retry(
                total=retries,
                status_forcelist=status_forcelist,
                backoff_factor=backoff_factor,
                allowed_methods=["GET", "HEAD"],
                respect_retry_after_header=True
            )
            
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            logger.info(f"Estrategia de reintentos configurada: {retries} reintentos, "
                      f"backoff={backoff_factor}s para códigos {status_forcelist}")
        except Exception as e:
            logger.error(f"Error configurando estrategia de reintentos: {e}")
            logger.warning("Continuando sin reintentos automáticos.")
    
    def _setup_fallback_session(self):
        """
        Configura una sesión alternativa con un contexto SSL más permisivo
        para sitios con problemas de certificados.
        """
        try:
            # Crear un contexto SSL más permisivo (solo se usará en último recurso)
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # Crear el adaptador con nuestro contexto SSL personalizado
            adapter = SSLContextAdapter(max_retries=1, ssl_context=context)
            
            # Montar el adaptador en la sesión de fallback
            self.fallback_session.mount('https://', adapter)
            logger.info("Sesión de fallback configurada para sitios con problemas de SSL")
        except Exception as e:
            logger.error(f"Error configurando sesión de fallback: {e}")
    
    def rotate_user_agent(self, session):
        """Rota aleatoriamente el User-Agent para evitar detección."""
        new_user_agent = random.choice(self.user_agents)
        session.headers.update({'User-Agent': new_user_agent})
        logger.debug(f"User-Agent rotado a: {new_user_agent}")
    
    def get(self, url: str, headers: Optional[Dict] = None, params: Optional[Dict] = None, 
            timeout: Optional[Tuple] = None, delay_after_request: float = DEFAULT_DELAY_SECONDS, 
            rotate_agent: bool = True, use_fallback: bool = False) -> Optional[requests.Response]:
        """
        Realiza una petición GET de forma inteligente.
        
        Args:
            url: URL a consultar
            headers: Headers adicionales
            params: Parámetros de consulta
            timeout: Timeout personalizado
            delay_after_request: Pausa tras la petición
            rotate_agent: Si se debe rotar el User-Agent
            use_fallback: Forzar el uso de la sesión de fallback
            
        Returns:
            Response si la petición fue exitosa, None si falló
        """
        self.stats['total_requests'] += 1
        domain = self._extract_domain(url)
        
        # Verificar si el dominio ha fallado repetidamente
        domain_failure_count = self.domain_failures.get(domain, 0)
        should_use_fallback = use_fallback or (domain_failure_count >= 2)
        
        # Elegir la sesión adecuada
        session = self.fallback_session if should_use_fallback else self.session
        
        # Rotar User-Agent si está habilitado
        if rotate_agent:
            self.rotate_user_agent(session)
        
        # Configurar delay con jitter para parecer más humano
        actual_delay = delay_after_request + random.uniform(0.1, 0.8)
        
        # Usar timeout específico o el predeterminado
        current_timeout = timeout if timeout is not None else self.default_timeout
        
        # Preparar headers
        request_headers = session.headers.copy()
        if headers:
            request_headers.update(headers)
        
        # Log de la petición
        logger.debug(f"Realizando petición GET a: {url}")
        if should_use_fallback:
            logger.info(f"Usando sesión de fallback para {domain} después de {domain_failure_count} fallos previos")
            self.stats['fallback_used'] += 1
        
        try:
            response = session.get(
                url,
                headers=request_headers,
                params=params,
                timeout=current_timeout,
                allow_redirects=True
            )
            
            # Verificar la respuesta
            response.raise_for_status()
            
            # Éxito
            logger.info(f"Petición GET a {url} exitosa (Código: {response.status_code}, "
                       f"Tamaño: {len(response.text)} bytes)")
            
            # Reiniciar contador de fallos del dominio
            if domain in self.domain_failures:
                del self.domain_failures[domain]
            
            # Actualizar estadísticas
            self.stats['successful_requests'] += 1
            
            # Hacer pausa
            if actual_delay > 0:
                logger.debug(f"Esperando {actual_delay:.2f} segundos antes de la siguiente petición...")
                time.sleep(actual_delay)
            
            return response
        
        except (ssl.SSLError, urllib3.exceptions.SSLError) as e:
            self.stats['ssl_errors'] += 1
            logger.error(f"Error SSL durante la petición a {url}: {e}")
            
            # Incrementar contador de fallos para este dominio
            self.domain_failures[domain] = domain_failure_count + 1
            
            # Si aún no estamos usando la sesión de fallback, intentar con ella
            if not should_use_fallback:
                logger.info(f"Reintentando con sesión de fallback debido a error SSL...")
                return self.get(url, headers, params, timeout, delay_after_request, 
                              rotate_agent, use_fallback=True)
            return None
        
        except requests.exceptions.Timeout as e:
            self.stats['failed_requests'] += 1
            logger.error(f"Timeout durante la petición GET a {url}. Error: {e}")
            return None
        
        except requests.exceptions.ConnectionError as e:
            self.stats['connection_errors'] += 1
            self.stats['failed_requests'] += 1
            logger.error(f"Error de conexión durante la petición GET a {url}. Error: {e}")
            
            # Incrementar contador de fallos para este dominio
            self.domain_failures[domain] = domain_failure_count + 1
            
            # Si aún no estamos usando la sesión de fallback, intentar con ella
            if not should_use_fallback and 'SSL' in str(e):
                logger.info(f"Reintentando con sesión de fallback debido a error de conexión SSL...")
                return self.get(url, headers, params, timeout, delay_after_request, 
                              rotate_agent, use_fallback=True)
            return None
        
        except requests.exceptions.HTTPError as e:
            self.stats['http_errors'] += 1
            self.stats['failed_requests'] += 1
            status_code = getattr(e.response, 'status_code', 'N/A')
            logger.error(f"Error HTTP {status_code} para {url}. Error: {e}")
            return None
        
        except Exception as e:
            self.stats['failed_requests'] += 1
            logger.exception(f"Error inesperado durante la petición GET a {url}: {e}")
            return None
    
    def _extract_domain(self, url: str) -> str:
        """Extrae el dominio de una URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            # Implementación simple de fallback
            url = url.replace('https://', '').replace('http://', '')
            domain = url.split('/')[0]
            return domain
    
    def get_stats(self) -> Dict[str, Any]:
        """Devuelve estadísticas del cliente HTTP."""
        if self.stats['total_requests'] > 0:
            success_rate = (self.stats['successful_requests'] / self.stats['total_requests']) * 100
            self.stats['success_rate'] = f"{success_rate:.1f}%"
        
        return self.stats
    
    def get_problematic_domains(self) -> Dict[str, int]:
        """Devuelve dominios con problemas y su contador de fallos."""
        return {domain: count for domain, count in self.domain_failures.items() if count > 0}
    
    def close(self):
        """Cierra las sesiones."""
        try:
            logger.info("Cerrando sesiones HTTPClient...")
            self.session.close()
            self.fallback_session.close()
            
            # Mostrar estadísticas de uso
            stats = self.get_stats()
            problematic_domains = self.get_problematic_domains()
            
            logger.info(f"Estadísticas del HTTPClient: {json.dumps(stats, indent=2)}")
            if problematic_domains:
                logger.warning(f"Dominios problemáticos: {json.dumps(problematic_domains, indent=2)}")
        except Exception as e:
            logger.error(f"Error al cerrar las sesiones HTTP: {e}", exc_info=True)

# Para compatibilidad con el código existente
HTTPClient = ImprovedHTTPClient
