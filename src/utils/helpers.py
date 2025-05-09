# -*- coding: utf-8 -*-
# /src/utils/helpers.py

"""
Módulo de Funciones de Ayuda (Helpers) Generales.

Nuestra caja de herramientas personal para el proyecto. Contiene funciones
pequeñas y reutilizables que no pertenecen a un módulo de utilidad más
específico, pero que nos ayudan a mantener el código limpio y DRY (Don't Repeat Yourself).

¡Si ves que repites la misma pequeña lógica en varios sitios,
quizás sea buena idea traerla aquí como una función helper!
"""

import logging
import re               # Para limpieza con expresiones regulares.
import unicodedata      # Para normalizar texto y quitar acentos.
from urllib.parse import urljoin # La forma más segura de unir URLs.
from typing import Optional, List, Dict, Any # Type hints.

# Logger para nuestras herramientas.
logger = logging.getLogger(__name__)

def normalize_text(text: Optional[str], remove_accents: bool = True, lowercase: bool = True) -> Optional[str]:
    """
    Normaliza una cadena de texto para facilitar comparaciones o búsquedas.

    Pasos que realiza:
    1. Quita espacios/saltos de línea al inicio y final.
    2. Reemplaza múltiples espacios/saltos de línea internos por un solo espacio.
    3. (Opcional) Convierte todo a minúsculas.
    4. (Opcional) Elimina acentos y diacríticos (ej: 'canción' -> 'cancion').

    Args:
        text (Optional[str]): El texto a normalizar.
        remove_accents (bool): Si es True, elimina acentos/diacríticos. Default: True.
        lowercase (bool): Si es True, convierte a minúsculas. Default: True.

    Returns:
        Optional[str]: El texto normalizado, o None si la entrada era None.
    """
    if text is None:
        return None
    if not isinstance(text, str):
        logger.warning(f"Se esperaba texto (str) para normalizar, pero se recibió {type(text)}. Devolviendo sin cambios.")
        return text

    try:
        # 1. y 2. Limpieza básica de espacios en blanco.
        normalized = re.sub(r'\s+', ' ', text).strip()

        # 3. Convertir a minúsculas (si se indica).
        if lowercase:
            normalized = normalized.lower()

        # 4. Quitar acentos/diacríticos (si se indica).
        #    Este es un método común y bastante efectivo en Python.
        #    NFKD descompone caracteres con acentos (ej: 'á' -> 'a' + '´').
        #    Luego codificamos a ASCII ignorando los caracteres no ASCII (los acentos '´').
        #    Finalmente, decodificamos de vuelta a utf-8.
        if remove_accents:
            # Normalización a NFKD (Normalization Form Compatibility Decomposition)
            nfkd_form = unicodedata.normalize('NFKD', normalized)
            # Codificar a ASCII ignorando caracteres no mapeables (los diacríticos)
            ascii_bytes = nfkd_form.encode('ASCII', 'ignore')
            # Decodificar de vuelta a string (utf-8 o la codificación deseada)
            normalized = ascii_bytes.decode('utf-8') # O usar 'ascii' si solo queremos ASCII puro

        return normalized if normalized else None # Devolver None si queda vacío

    except Exception as e:
         logger.error(f"Error al normalizar texto: '{str(text)[:100]}...'. Error: {e}", exc_info=True)
         return text # Devolver el texto original si falla la normalización


def safe_url_join(base_url: Optional[str], relative_path: Optional[str]) -> Optional[str]:
    """
    Une de forma segura una URL base con una ruta relativa.

    Usa urljoin de urllib.parse, que maneja correctamente las barras '/'
    y diferentes escenarios (si path es absoluto, si base tiene path, etc.).

    Args:
        base_url (Optional[str]): La URL base (ej: 'https://www.ejemplo.com/directorio/').
        relative_path (Optional[str]): La ruta relativa a unir (ej: '../pagina.html', 'recurso.jpg', '/otro/path').

    Returns:
        Optional[str]: La URL absoluta resultante, o None si las entradas son inválidas.
    """
    if not base_url or not relative_path:
        # logger.debug(f"No se puede unir URL. Base: '{base_url}', Relativa: '{relative_path}'")
        return None # No podemos unir si falta alguna parte.

    if not isinstance(base_url, str) or not isinstance(relative_path, str):
         logger.warning(f"Se esperaban strings para unir URLs, recibido: {type(base_url)}, {type(relative_path)}")
         return None

    try:
        # urljoin es la forma más robusta y estándar en Python para esto.
        joined_url = urljoin(base_url, relative_path)
        # Una verificación simple por si acaso urljoin devuelve algo inesperado
        if not isinstance(joined_url, str) or not joined_url.startswith('http'):
             logger.warning(f"urljoin devolvió un resultado inesperado o no absoluto: '{joined_url}' desde base '{base_url}' y path '{relative_path}'")
             # Podríamos intentar devolver None o el resultado tal cual. Devolvamos None si no parece URL válida.
             return None
        return joined_url
    except ValueError as e:
        # urljoin puede lanzar ValueError si la URL base es muy inválida (ej: esquema desconocido)
        logger.error(f"Error de valor al unir URLs: Base='{base_url}', Relativa='{relative_path}'. Error: {e}")
        return None
    except Exception as e:
         logger.error(f"Error inesperado al unir URLs: Base='{base_url}', Relativa='{relative_path}'. Error: {e}", exc_info=True)
         return None


# --- Podríamos añadir más helpers aquí en el futuro ---
# Ej: parse_date_flexible, extract_emails_from_text, etc.


# --- Ejemplo de Uso ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

    print("--- Probando helpers.py ---")

    # Prueba de normalize_text
    print("\n--- Probando normalize_text ---")
    textos_prueba = [
        "  Analista de   Datos con Énfasis en SQL y Python ",
        "Ingeniería de Software (Backend)",
        "Çiência de Dádös Avançáda",
        "REMOTO - España",
        None,
        "   ",
        12345 # Tipo incorrecto
    ]
    for texto in textos_prueba:
        normal_con_acento = normalize_text(texto, remove_accents=False)
        normal_sin_acento = normalize_text(texto, remove_accents=True)
        print(f"Original: '{texto}'")
        print(f"  -> Normal (con acento): '{normal_con_acento}'")
        print(f"  -> Normal (sin acento): '{normal_sin_acento}'")

    # Prueba de safe_url_join
    print("\n--- Probando safe_url_join ---")
    pruebas_url = [
        ("https://www.ejemplo.com/path1/", "oferta.html"),
        ("https://www.ejemplo.com/path1/", "/otra/oferta.html"),
        ("https://www.ejemplo.com/path1/", "../oferta_arriba.html"),
        ("https://www.ejemplo.com/path1/pagina.html", "recurso.jpg"),
        ("https://www.ejemplo.com/path1/", "https://www.otrodominio.com/pagina"), # Path absoluto
        ("https://www.ejemplo.com", "trabajos/123"),
        ("https://www.ejemplo.com/", "/trabajos/123"),
        (None, "path/"),
        ("https://base.com", None),
        ("ftp://ftp.ejemplo.com", "archivo.zip"), # urljoin maneja otros esquemas
        ("esto no es url", "path") # Base inválida
    ]
    for base, rel in pruebas_url:
         resultado = safe_url_join(base, rel)
         print(f"Base: '{base}', Relativa: '{rel}' -> Unida: '{resultado}'")