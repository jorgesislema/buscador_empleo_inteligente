# -*- coding: utf-8 -*-
# /src/utils/http_client.py

"""
Nuestro Cliente HTTP Personalizado.

Este módulo nos proporciona una forma centralizada y robusta de hacer
peticiones HTTP (principalmente GET por ahora) a las páginas web y APIs.
La idea es encapsular aquí las buenas prácticas:
- Usar una sesión de requests para eficiencia.
- Poner un User-Agent decente para no parecer un script simple.
- Implementar reintentos automáticos si algo falla temporalmente.
- Añadir pausas configurables entre peticiones.
- Manejar errores comunes y registrarlos con nuestro logger.
"""

import requests # La librería estrella para hacer peticiones HTTP.
# Clases necesarias de requests y urllib3 para configurar los reintentos.
# ¡Ojo! urllib3 es una dependencia de requests, así que normalmente ya está instalada.
try:
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("ERROR: Necesitas instalar la librería 'requests' (pip install requests)")
    # Definir clases dummy para que el script cargue, aunque no funcionará.
    class HTTPAdapter: pass
    class Retry: pass

import time     # Para poder hacer pausas (time.sleep).
import logging  # Para registrar lo que hace nuestro cliente.
import random   # Podríamos usarlo para añadir un poquito de aleatoriedad a las pausas.
from typing import Optional, Dict, Any, Tuple # Type hints

# Obtenemos el logger para este módulo. Usará la config que ya definimos.
logger = logging.getLogger(__name__)

# --- Constantes y Configuraciones por Defecto ---

# Un User-Agent más o menos estándar de un navegador. Es buena idea rotarlo
# o hacerlo configurable en el futuro, pero empecemos con uno fijo.
DEFAULT_USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36') # Actualizado un poco

# Tiempo máximo de espera para conectar y para leer la respuesta (en segundos).
DEFAULT_TIMEOUT = (15, 45) # (timeout conexión, timeout lectura) - Aumentado un poco

# Pausa por defecto en segundos después de cada petición exitosa.
# ¡Importante para no sobrecargar servidores ni ser bloqueados!
DEFAULT_DELAY_SECONDS = 1.5

# Configuración de reintentos:
DEFAULT_RETRIES = 3 # Número total de reintentos a intentar.
DEFAULT_BACKOFF_FACTOR = 0.8 # Factor de espera exponencial entre reintentos (0.8 * 2^0, 0.8 * 2^1, 0.8 * 2^2...)
                             # sleep_time = backoff_factor * (2 ** ({retry number} - 1))
                             # ej: 0s(1ª), 0.8s(2ª), 1.6s(3ª)... (urllib3 añade algo de jitter también)
STATUS_CODES_TO_RETRY = [429, 500, 502, 503, 504] # Códigos HTTP que activarán un reintento.
                                                 # 429: Too Many Requests, 5xx: Server Errors.

class HTTPClient:
    """
    Una clase que gestiona una sesión de requests con configuración personalizada.

    Se encarga de centralizar las peticiones GET, aplicando User-Agent,
    reintentos, timeouts y delays de forma consistente.
    """
    def __init__(self, user_agent=DEFAULT_USER_AGENT, timeout=DEFAULT_TIMEOUT,
                 retries=DEFAULT_RETRIES, backoff_factor=DEFAULT_BACKOFF_FACTOR,
                 status_forcelist=STATUS_CODES_TO_RETRY):
        """
        Inicializamos nuestra sesión de requests y aplicamos la configuración.

        Args:
            user_agent (str): El User-Agent a usar.
            timeout (tuple): Timeout de conexión y lectura.
            retries (int): Número máximo de reintentos.
            backoff_factor (float): Factor para el cálculo del tiempo de espera exponencial entre reintentos.
            status_forcelist (list): Lista de códigos de estado HTTP que deben provocar un reintento.
        """
        logger.info("Inicializando el HTTPClient...")
        # Creamos la sesión. ¡La usaremos para todas las peticiones!
        self.session = requests.Session()

        # Establecemos el User-Agent por defecto para toda la sesión.
        self.session.headers.update({'User-Agent': user_agent})
        logger.debug(f"User-Agent configurado para la sesión: {user_agent}")

        # Guardamos el timeout por defecto para usarlo en las peticiones.
        self.default_timeout = timeout

        # --- Configuración de la Estrategia de Reintentos ---
        # Aquí definimos cómo queremos que se comporte la librería ante fallos.
        try:
            retry_strategy = Retry(
                total=retries, # Número total de reintentos.
                status_forcelist=status_forcelist, # Códigos de estado que fuerzan el reintento.
                backoff_factor=backoff_factor, # ¡El factor de espera exponencial!
                # Podríamos añadir method_whitelist=['GET'] si solo queremos reintentar GETs,
                # pero por defecto ya suele ser así para métodos seguros como GET.
                # También podríamos añadir 'allowed_methods' si quisiéramos reintentar otros.
            )

            # Creamos un "adaptador" HTTP al que le enchufamos nuestra estrategia de reintentos.
            adapter = HTTPAdapter(max_retries=retry_strategy)

            # "Montamos" este adaptador en nuestra sesión para que se aplique
            # tanto a las URLs que empiezan por http:// como por https://.
            self.session.mount('http://', adapter)
            self.session.mount('https://', adapter)
            logger.info(f"Estrategia de reintentos configurada: {retries} reintentos, backoff={backoff_factor}s para códigos {status_forcelist}")
        except TypeError as e:
             logger.error(f"Error configurando Retry/HTTPAdapter (¿versión urllib3/requests incompatible?): {e}")
             logger.warning("Continuando sin reintentos automáticos.")
        except Exception as e:
            logger.exception(f"Error inesperado configurando reintentos: {e}")
            logger.warning("Continuando sin reintentos automáticos.")


    def get(self, url: str, headers: Optional[Dict] = None, params: Optional[Dict] = None, timeout: Optional[Tuple] = None,
            delay_after_request: float = DEFAULT_DELAY_SECONDS) -> Optional[requests.Response]:
        """
        Realiza una petición GET a la URL especificada usando nuestra sesión configurada.

        Args:
            url (str): La URL a la que hacer la petición GET.
            headers (dict, optional): Cabeceras adicionales o para sobreescribir las de la sesión. Defaults to None.
            params (dict, optional): Parámetros a añadir a la URL (ej: {'q': 'python'}). Defaults to None.
            timeout (tuple, optional): Timeout específico para esta petición (conexión, lectura). Usa el default si es None. Defaults to None.
            delay_after_request (float, optional): Pausa en segundos después de una petición exitosa. Defaults to DEFAULT_DELAY_SECONDS.

        Returns:
            requests.Response | None: El objeto Response si la petición fue exitosa (después de posibles reintentos),
                                     o None si la petición falló definitivamente.
        """
        # Usamos el timeout específico si se proporciona, si no, el default de la clase.
        current_timeout = timeout if timeout is not None else self.default_timeout

        # Preparamos las cabeceras: empezamos con las de la sesión y actualizamos/añadimos las específicas si se pasan.
        request_headers = self.session.headers.copy() # Copiamos para no modificar las de la sesión permanentemente.
        if headers:
            request_headers.update(headers)

        logger.debug(f"Realizando petición GET a: {url}")
        if params: logger.debug(f"  -> Params: {params}")
        # No logueamos headers por defecto por si contienen info sensible. Descomentar si es necesario depurar.
        # logger.debug(f"  -> Headers: {request_headers}")
        logger.debug(f"  -> Timeout: {current_timeout}s")

        response = None # Inicializamos la respuesta como None.
        try:
            # ¡Aquí ocurre la magia! Hacemos la petición GET con nuestra sesión.
            # La sesión aplicará automáticamente los reintentos si es necesario (si configuramos el adapter bien).
            response = self.session.get(
                url,
                headers=request_headers,
                params=params,
                timeout=current_timeout,
                # stream=True podría ser útil para archivos grandes, pero no usualmente para APIs/scraping.
                # verify=True es el default y es importante para verificar certificados SSL. ¡No poner a False a la ligera!
            )

            # Verificamos el código de estado DESPUÉS de que los reintentos (si los hubo) terminaron.
            # raise_for_status() lanzará una excepción HTTPError para códigos 4xx (error cliente) o 5xx (error servidor).
            response.raise_for_status()

            # ¡Éxito! Si llegamos aquí, la petición fue bien (código 2xx).
            logger.info(f"Petición GET a {url} exitosa (Código: {response.status_code})")

            # ¡La pausa! Esperamos un poquito después de una petición exitosa.
            # Podríamos añadir algo de aleatoriedad si quisiéramos ser menos predecibles.
            # delay_with_jitter = delay_after_request + random.uniform(0, 0.5) # Ejemplo jitter
            if delay_after_request > 0:
                 logger.debug(f"Esperando {delay_after_request} segundos antes de la siguiente petición...")
                 time.sleep(delay_after_request)

            # Devolvemos el objeto Response completo. El que llama decidirá qué hacer con él (leer .text, .json(), etc.).
            return response

        except requests.exceptions.Timeout as e:
             logger.error(f"Timeout durante la petición GET a {url}. Error: {e}")
             return None # Devolvemos None en caso de timeout
        except requests.exceptions.ConnectionError as e:
             logger.error(f"Error de conexión durante la petición GET a {url}. ¿URL válida? ¿Hay red? Error: {e}")
             return None
        except requests.exceptions.HTTPError as e:
             # Este error lo lanza raise_for_status() para códigos 4xx/5xx que NO fueron reintentados o fallaron todos los reintentos.
             status_code = getattr(e.response, 'status_code', 'N/A')
             logger.error(f"Error HTTP {status_code} para {url} después de reintentos (si aplicaban). Error: {e}")
             # Es importante devolver None para que el scraper/cliente sepa que falló.
             return None
        except requests.exceptions.RequestException as e:
            # Capturamos cualquier otra excepción base de requests.
            status_code = getattr(e.response, 'status_code', 'N/A')
            logger.error(f"Falló la petición GET a {url}. Código: {status_code}. Error: {e}")
            return None
        except Exception as e:
             # Capturamos cualquier otro error inesperado que no sea de requests.
             logger.exception(f"Error inesperado durante la petición GET a {url}: {e}") # Usamos logger.exception para incluir traceback.
             return None

    # Podríamos añadir un método post() si alguna API lo necesitara,
    # configurando también los reintentos para POST si fuera seguro hacerlo.
    # def post(self, url: str, data: Optional[Dict] = None, json: Optional[Dict] = None, ...) -> Optional[requests.Response]: ...

    def close(self):
        """
        Cierra la sesión de requests subyacente.
        Es buena práctica llamarlo cuando ya no se necesite el cliente,
        especialmente si la aplicación va a terminar.
        """
        if self.session:
            try:
                logger.info("Cerrando la sesión HTTPClient.")
                self.session.close()
            except Exception as e:
                 logger.error(f"Error al cerrar la sesión HTTP: {e}", exc_info=True)

# --- Ejemplo de Uso (si ejecutamos este script directamente) ---
if __name__ == '__main__':
    # Configuración rápida de logging para la prueba.
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')

    print("--- Probando el HTTPClient ---")
    # Creamos una instancia de nuestro cliente.
    cliente = HTTPClient(retries=2, backoff_factor=0.3) # Probar con menos reintentos y backoff más corto

    # --- Prueba 1: URL válida ---
    print("\n[Prueba 1: URL válida (httpbin.org)]")
    respuesta_ok = cliente.get('https://httpbin.org/get?info=prueba1', delay_after_request=0.5) # Delay más corto para prueba
    if respuesta_ok:
        print(f"-> Éxito! Código: {respuesta_ok.status_code}")
        # print(f"-> Respuesta (JSON): {respuesta_ok.json()}")
    else:
        print("-> Falló la petición.")

    # --- Prueba 2: URL que da error 404 ---
    print("\n[Prueba 2: URL que no existe (Error 404)]")
    respuesta_404 = cliente.get('https://httpbin.org/status/404', delay_after_request=0.5)
    if respuesta_404:
        print(f"-> Éxito inesperado! Código: {respuesta_404.status_code}")
    else:
        print("-> Falló la petición (esperado, por Error 404).")

    # --- Prueba 3: URL que da error 503 (Probando reintentos) ---
    print("\n[Prueba 3: URL que da Error 503 (Probando reintentos)]")
    # httpbin puede simular errores. Probamos 503 que está en nuestra lista de reintento.
    respuesta_503 = cliente.get('https://httpbin.org/status/503', delay_after_request=0.5)
    # Si los reintentos fallan todas las veces, devolverá None.
    if respuesta_503:
        print(f"-> Éxito inesperado! Código: {respuesta_503.status_code}")
    else:
        print("-> Falló la petición (esperado, por Error 503 tras reintentos). Revisa los logs DEBUG para ver los reintentos.")

    # --- Prueba 4: URL con timeout ---
    print("\n[Prueba 4: URL con timeout corto]")
    # httpbin permite simular retrasos. Pedimos un retraso de 5s con timeout de 2s.
    respuesta_timeout = cliente.get('https://httpbin.org/delay/5', timeout=(2, 2), delay_after_request=0.5) # Timeout corto (conexión, lectura)
    if respuesta_timeout:
        print(f"-> Éxito inesperado! Código: {respuesta_timeout.status_code}")
    else:
        print("-> Falló la petición (esperado, por Timeout).")


    # Cerramos la sesión al final.
    cliente.close()