# test_print.py
print("Prueba de salida")
print("Versión de Python:")
import sys
print(sys.version)
import importlib
print("Módulos disponibles:")
print("os:", importlib.__name__)
try:
    import src
    print("src:", src.__name__)
except ImportError:
    print("src: No disponible")
print("Fin de la prueba")
