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
from datetime import datetime, timedelta # Para manejo de fechas.

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
    if not base_url:
        return None # No podemos unir si falta la base.
    if relative_path is None:
        return None
    if not isinstance(base_url, str) or not isinstance(relative_path, str):
         logger.warning(f"Se esperaban strings para unir URLs, recibido: {type(base_url)}, {type(relative_path)}")
         return None
    if relative_path == "":
        # Si el path es vacío, devolvemos la base (comportamiento estándar de urljoin)
        return base_url
    try:
        # urljoin es la forma más robusta y estándar en Python para esto.
        joined_url = urljoin(base_url, relative_path)
        # Una verificación simple por si acaso urljoin devuelve algo inesperado
        # Aceptar cualquier esquema válido (http, https, ftp, etc.)
        if not isinstance(joined_url, str) or not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', joined_url):
             logger.warning(f"urljoin devolvió un resultado inesperado o no absoluto: '{joined_url}' desde base '{base_url}' y path '{relative_path}'")
             return None
        return joined_url
    except ValueError as e:
        # urljoin puede lanzar ValueError si la URL base es muy inválida (ej: esquema desconocido)
        logger.error(f"Error de valor al unir URLs: Base='{base_url}', Relativa='{relative_path}'. Error: {e}")
        return None
    except Exception as e:
         logger.error(f"Error inesperado al unir URLs: Base='{base_url}', Relativa='{relative_path}'. Error: {e}", exc_info=True)
         return None


def process_date(date_str):
    """
    Procesa y estandariza fechas de diferentes formatos (inglés y español)
    y devuelve en formato ISO 'YYYY-MM-DD'.
    
    Args:
        date_str: La cadena de fecha a procesar (puede ser en español/inglés, relativa o absoluta)
    
    Returns:
        str: Fecha en formato ISO 'YYYY-MM-DD' o None si no se puede procesar
    """
    if not date_str:
        return None
    
    date_str = str(date_str).lower().strip()
    today = datetime.now().date()
    
    # Si ya está en formato ISO, devolverlo directamente
    iso_match = re.match(r'^\d{4}-\d{2}-\d{2}', date_str)
    if iso_match:
        return date_str[:10]  # Solo los primeros 10 caracteres (YYYY-MM-DD)
    
    # Formatos relativos en español
    if any(term in date_str for term in ['hoy', 'publicado hoy', 'publicada hoy']):
        return today.strftime('%Y-%m-%d')
    if any(term in date_str for term in ['ayer', 'publicado ayer', 'publicada ayer']):
        return (today - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Formatos relativos en inglés
    if any(term in date_str for term in ['today', 'posted today', 'just now', 'moments ago']):
        return today.strftime('%Y-%m-%d')
    if any(term in date_str for term in ['yesterday', 'posted yesterday']):
        return (today - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Formato "hace X días/horas/etc." (español)
    match_es = re.search(r'hace\s+(\d+)\s+(día|días|hora|horas|semana|semanas|mes|meses)', date_str)
    if match_es:
        value = int(match_es.group(1))
        unit = match_es.group(2)
        
        if 'día' in unit:
            return (today - timedelta(days=value)).strftime('%Y-%m-%d')
        elif 'hora' in unit:
            return today.strftime('%Y-%m-%d')  # Mismo día para horas
        elif 'semana' in unit:
            return (today - timedelta(weeks=value)).strftime('%Y-%m-%d')
        elif 'mes' in unit:
            return (today - timedelta(days=value * 30)).strftime('%Y-%m-%d')
    
    # Formato "publicado hace X días/horas"
    match_pub_es = re.search(r'publicad[oa]\s+hace\s+(\d+)\s+(día|días|hora|horas|semana|semanas|mes|meses)', date_str)
    if match_pub_es:
        value = int(match_pub_es.group(1))
        unit = match_pub_es.group(2)
        
        if 'día' in unit:
            return (today - timedelta(days=value)).strftime('%Y-%m-%d')
        elif 'hora' in unit:
            return today.strftime('%Y-%m-%d')
        elif 'semana' in unit:
            return (today - timedelta(weeks=value)).strftime('%Y-%m-%d')
        elif 'mes' in unit:
            return (today - timedelta(days=value * 30)).strftime('%Y-%m-%d')
    
    # Formato "X days/hours ago" (inglés)
    match_en = re.search(r'(\d+)\s+(day|days|hour|hours|week|weeks|month|months)(?:\s+ago)?', date_str)
    if match_en:
        value = int(match_en.group(1))
        unit = match_en.group(2)
        
        if 'day' in unit:
            return (today - timedelta(days=value)).strftime('%Y-%m-%d')
        elif 'hour' in unit:
            return today.strftime('%Y-%m-%d')  # Mismo día para horas
        elif 'week' in unit:
            return (today - timedelta(weeks=value)).strftime('%Y-%m-%d')
        elif 'month' in unit:
            return (today - timedelta(days=value * 30)).strftime('%Y-%m-%d')
    
    # Formato "posted X days/hours ago" (inglés)
    match_posted = re.search(r'posted\s+(\d+)\s+(day|days|hour|hours|week|weeks|month|months)(?:\s+ago)?', date_str)
    if match_posted:
        value = int(match_posted.group(1))
        unit = match_posted.group(2)
        
        if 'day' in unit:
            return (today - timedelta(days=value)).strftime('%Y-%m-%d')
        elif 'hour' in unit:
            return today.strftime('%Y-%m-%d')
        elif 'week' in unit:
            return (today - timedelta(weeks=value)).strftime('%Y-%m-%d')
        elif 'month' in unit:
            return (today - timedelta(days=value * 30)).strftime('%Y-%m-%d')
    
    # Formatos de fecha específicos (varios idiomas)
    # Primero intentamos formatos más estrictos
    date_formats = [
        '%Y-%m-%d',       # ISO: 2023-05-01
        '%Y/%m/%d',       # ISO alternativo: 2023/05/01
        '%d/%m/%Y',       # Español: 01/05/2023
        '%m/%d/%Y',       # US: 05/01/2023
        '%d-%m-%Y',       # Alternativo: 01-05-2023
        '%m-%d-%Y',       # US alternativo: 05-01-2023
        '%Y-%m-%dT%H:%M', # ISO con hora
        '%Y-%m-%d %H:%M:%S', # ISO con hora y segundos
    ]
    
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            return parsed_date.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # Intentar con formatos con nombres de mes
    # Lista de meses en español e inglés para reemplazar en el texto
    months_es = {
        'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
        'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
        'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
    }
    
    months_en = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    
    # Abreviaturas de meses
    months_abbr_es = {
        'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'ago': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12'
    }
    
    months_abbr_en = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }
    
    # Intento con expresiones regulares para formatos con nombre de mes
    # Patrón español: 15 de mayo de 2023, 15-mayo-2023, etc.
    pattern_es = r'(\d{1,2})(?:\s+de)?\s+([a-zé]+)(?:\s+de)?\s+(\d{4})'
    match_es = re.search(pattern_es, date_str)
    if match_es:
        day = match_es.group(1).zfill(2)
        month_name = match_es.group(2).lower()
        year = match_es.group(3)
        
        # Buscar el mes en los diccionarios
        month = None
        for m_dict in [months_es, months_abbr_es]:
            if month_name in m_dict:
                month = m_dict[month_name]
                break
        
        if month and day and year:
            return f"{year}-{month}-{day}"
    
    # Patrón inglés: May 15, 2023, May 15 2023, 15 May 2023, etc.
    pattern_en1 = r'([a-z]+)\s+(\d{1,2})(?:,|\s+)?\s+(\d{4})'  # May 15, 2023
    pattern_en2 = r'(\d{1,2})(?:\s+of)?\s+([a-z]+)(?:,|\s+)?\s+(\d{4})'  # 15 May 2023
    
    for pattern in [pattern_en1, pattern_en2]:
        match_en = re.search(pattern, date_str)
        if match_en:
            if pattern == pattern_en1:
                month_name = match_en.group(1).lower()
                day = match_en.group(2).zfill(2)
            else:
                day = match_en.group(1).zfill(2)
                month_name = match_en.group(2).lower()
                
            year = match_en.group(3)
            
            # Buscar el mes en los diccionarios
            month = None
            for m_dict in [months_en, months_abbr_en]:
                if month_name in m_dict:
                    month = m_dict[month_name]
                    break
            
            if month and day and year:
                return f"{year}-{month}-{day}"
    
    # Si llegamos aquí, no pudimos parsear la fecha
    logger.warning(f"No se pudo parsear la fecha: '{date_str}'")
    return None  # Devolvemos None si no se puede interpretar la fecha


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
        ("esto no es url", "path"), # Base inválida
        ("https://www.ejemplo.com", "") # Relativa vacía
    ]
    for base, rel in pruebas_url:
         resultado = safe_url_join(base, rel)
         print(f"Base: '{base}', Relativa: '{rel}' -> Unida: '{resultado}'")

    # Prueba de process_date
    print("\n--- Probando process_date ---")
    fechas_prueba = [
        "hoy",
        "ayer",
        "hace 3 días",
        "2 weeks ago",
        "01/05/2023",
        "May 1, 2023",
        "01 de Mayo de 2023",
        "esto no es una fecha"
    ]
    for fecha in fechas_prueba:
        resultado_fecha = process_date(fecha)
        print(f"Fecha original: '{fecha}' -> Procesada: '{resultado_fecha}'")