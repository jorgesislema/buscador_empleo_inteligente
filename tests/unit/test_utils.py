# -*- coding: utf-8 -*-
# /tests/unit/test_utils.py

"""
Pruebas Unitarias para los Módulos de Utilidades (helpers, config_loader).

Aquí probamos nuestras herramientas de la "caja de herramientas" (`helpers.py`)
y partes específicas de otros utils como `config_loader.get_secret`.
Queremos estar seguros de que estas funciones pequeñas pero importantes
hacen exactamente lo que deben en diferentes escenarios.
"""

import pytest   # Framework de pruebas
import logging  # Para verificar logs con caplog
import os       # Para interactuar con variables de entorno (aunque monkeypatch lo facilita)
import sys
from pathlib import Path

# Añadimos la raíz del proyecto para poder importar desde src
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Importamos las funciones/clases que vamos a probar
from src.utils import helpers
from src.utils.config_loader import get_secret

# --- Pruebas para helpers.py ---

# Usamos parametrize para probar muchos casos de normalize_text fácilmente
@pytest.mark.parametrize(
    "input_text, remove_accents, lowercase, expected_output",
    [
        # Casos básicos
        ("  Texto con Espacios  \n\t", True, True, "texto con espacios"),
        ("Texto Con Mayúsculas", True, True, "texto con mayusculas"),
        ("Texto Sin Cambios", True, False, "Texto Sin Cambios"), # lowercase=False
        # Pruebas de acentos
        ("Canción Ñandú Pingüino", True, True, "cancion nandu pinguino"), # Quitar acentos (default)
        ("Canción Ñandú Pingüino", False, True, "canción ñandú pingüino"), # Mantener acentos
        ("Çödïgò Èspecial", True, True, "codigo especial"),
        # Combinados
        ("  Mezcla CON Acentos y EspaCIos  ", True, True, "mezcla con acentos y espacios"),
        ("  Mezcla CON Acentos y EspaCIos  ", False, True, "mezcla con acentos y espacios"),# Mantener acentos -> ¡OJO! el lower sí se aplica
        ("  Mezcla CON Acentos y EspaCIos  ", False, False, "Mezcla CON Acentos y EspaCIos"),# Mantener acentos y case
        # Casos borde
        ("", True, True, None), # String vacío debería ser None después de strip()
        ("   ", True, True, None), # String solo con espacios
        (None, True, True, None), # Entrada None
        # (Opcional: Probar con tipos incorrectos, aunque la función ya loguea warning)
        # (12345, True, True, 12345), # Tipo incorrecto, debería devolverlo tal cual
    ],
    ids=[ # Nombres descriptivos para cada caso de prueba
        "limpieza_espacios", "solo_lowercase", "solo_acentos_no_lower",
        "quitar_acentos_basico", "mantener_acentos", "quitar_acentos_raros",
        "combinado_quita_acentos", "combinado_mantiene_acentos", "combinado_sin_cambios",
        "string_vacio", "solo_espacios", "input_none",
        # "tipo_incorrecto"
    ]
)
def test_normalize_text(input_text, remove_accents, lowercase, expected_output):
    """Prueba la función helpers.normalize_text con varios casos."""
    print(f"\nTEST: normalize_text('{input_text}', remove_accents={remove_accents}, lowercase={lowercase}) -> Esperado: '{expected_output}'")
    assert helpers.normalize_text(input_text, remove_accents=remove_accents, lowercase=lowercase) == expected_output

# Pruebas para safe_url_join
@pytest.mark.parametrize(
    "base, relative, expected_output",
    [
        # Casos básicos
        ("https://www.ejemplo.com/path1/", "oferta.html", "https://www.ejemplo.com/path1/oferta.html"),
        ("https://www.ejemplo.com/path1/", "/otra/oferta.html", "https://www.ejemplo.com/otra/oferta.html"), # Path absoluto desde raíz
        ("https://www.ejemplo.com/path1/", "../oferta_arriba.html", "https://www.ejemplo.com/oferta_arriba.html"), # Subir nivel
        ("https://www.ejemplo.com/path1/pagina.html", "recurso.jpg", "https://www.ejemplo.com/path1/recurso.jpg"), # Relativo a página
        ("https://www.ejemplo.com/path1/", "https://www.otrodominio.com/pagina", "https://www.otrodominio.com/pagina"), # Path ya es absoluto
        ("https://www.ejemplo.com", "trabajos/123", "https://www.ejemplo.com/trabajos/123"), # Base sin slash final
        ("https://www.ejemplo.com/", "/trabajos/123", "https://www.ejemplo.com/trabajos/123"), # Base con slash, path con slash
        # Casos borde
        (None, "path/", None),
        ("https://base.com", None, None),
        ("", "path", None), # Base vacía no es válida para urljoin
        ("https://base.com", "", "https://base.com"), # Path vacío devuelve la base
        # Otros esquemas
        ("ftp://ftp.ejemplo.com", "archivo.zip", "ftp://ftp.ejemplo.com/archivo.zip"),
        # Base inválida (urljoin puede ser permisivo, pero nuestra validación extra debería devolver None)
        ("esto no es url", "path", None),
    ],
    ids=[
        "relativo_simple", "absoluto_desde_raiz", "subir_nivel", "relativo_a_pagina",
        "path_ya_absoluto", "base_sin_slash", "base_y_path_con_slash",
        "base_none", "relativa_none", "base_vacia", "relativa_vacia",
        "otro_esquema", "base_invalida"
    ]
)
def test_safe_url_join(base, relative, expected_output):
    """Prueba la función helpers.safe_url_join con varios casos."""
    print(f"\nTEST: safe_url_join('{base}', '{relative}') -> Esperado: '{expected_output}'")
    assert helpers.safe_url_join(base, relative) == expected_output


# --- Pruebas para config_loader.get_secret ---

# Usamos monkeypatch para simular variables de entorno sin afectar el sistema real.
def test_get_secret_exists(monkeypatch):
    """Prueba obtener un secreto que sí existe en las variables de entorno."""
    print("\nTEST: test_get_secret_exists")
    secret_key = "MI_TEST_SECRET_KEY"
    secret_value = "12345abcdef"
    # Simulamos que la variable de entorno existe
    monkeypatch.setenv(secret_key, secret_value)
    # Verificamos que get_secret la devuelve correctamente
    assert get_secret(secret_key) == secret_value
    # Limpiamos la variable simulada (monkeypatch lo hace automáticamente al final del test, pero es buena práctica)
    # monkeypatch.delenv(secret_key)

def test_get_secret_not_exists(monkeypatch, caplog):
    """Prueba obtener un secreto que NO existe (sin default)."""
    print("\nTEST: test_get_secret_not_exists")
    secret_key = "MI_TEST_SECRET_INEXISTENTE"
    # Nos aseguramos de que NO exista (por si acaso existía antes)
    monkeypatch.delenv(secret_key, raising=False) # raising=False evita error si no existía
    # Verificamos que devuelve None
    assert get_secret(secret_key) is None
    # Verificamos que se registró una advertencia en el log usando caplog
    assert f"Variable de entorno/secreto '{secret_key}' no encontrada" in caplog.text

def test_get_secret_not_exists_with_default(monkeypatch):
    """Prueba obtener un secreto que NO existe, pero con un valor default."""
    print("\nTEST: test_get_secret_not_exists_with_default")
    secret_key = "MI_TEST_SECRET_INEXISTENTE_2"
    default_value = "valor_por_defecto"
    monkeypatch.delenv(secret_key, raising=False)
    # Verificamos que devuelve el valor default
    assert get_secret(secret_key, default=default_value) == default_value

def test_get_secret_placeholder_warning(monkeypatch, caplog):
    """Prueba que get_secret detecta y advierte sobre placeholders."""
    print("\nTEST: test_get_secret_placeholder_warning")
    secret_key = "MI_TEST_SECRET_PLACEHOLDER"
    placeholder_value = "TU_API_KEY_AQUI"
    # Simulamos que la variable tiene un placeholder
    monkeypatch.setenv(secret_key, placeholder_value)

    # Configuramos el nivel de log para capturar el ERROR
    caplog.set_level(logging.ERROR)

    # Verificamos que devuelve el placeholder (la función actual no lo bloquea)
    assert get_secret(secret_key) == placeholder_value
    # Verificamos que se registró el mensaje de ERROR sobre el placeholder
    assert f"¡ALERTA! El valor para '{secret_key}' ('{placeholder_value}') parece un placeholder" in caplog.text

# --- Fin de las Pruebas ---