#!/usr/bin/env python
# -*- coding: utf-8 -*-
# test_diagnostic.py

"""
Script de diagnóstico para verificar la estructura y sintaxis de los archivos del proyecto.
"""

import os
import sys

# Mostrar la versión de Python
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}\n")

# Intentar importar los módulos principales uno por uno
modules = [
    "src",
    "src.utils",
    "src.utils.config_loader",
    "src.utils.http_client",
    "src.core.job_filter",
    "src.persistence.database_manager",
    "src.super_pipeline"
]

print("Intentando importar módulos principales...\n")

for module in modules:
    try:
        __import__(module)
        print(f"✅ {module}: Importado correctamente")
    except ImportError as e:
        print(f"❌ {module}: Error de importación - {e}")
    except SyntaxError as e:
        print(f"❌ {module}: Error de sintaxis - {e}")
        print(f"   En archivo: {e.filename}, línea {e.lineno}")
        print(f"   Mensaje: {e.msg}")
    except Exception as e:
        print(f"❌ {module}: Error inesperado - {e}")

print("\nFinalizado diagnóstico básico de importación")
