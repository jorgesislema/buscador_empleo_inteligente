# -*- coding: utf-8 -*-
# /src/apis/__init__.py

"""
Módulo de Clientes de API para fuentes de trabajo.
Contiene todas las implementaciones específicas de clientes para distintas APIs.
"""

from src.apis.base_api import BaseAPIClient
from src.apis.adzuna_client import AdzunaClient
from src.apis.arbeitnow_client import ArbeitnowClient
from src.apis.jobicy_client import JobicyClient
from src.apis.jooble_client import JoobleClient
from src.apis.remoteok_client import RemoteOkClient
from src.apis.huggingface_client import HuggingFaceClient

# Hacer disponibles los clientes para importación directa desde el módulo
__all__ = [
    'BaseAPIClient',
    'AdzunaClient', 
    'ArbeitnowClient',
    'JobicyClient',
    'JoobleClient',
    'RemoteOkClient',
    'HuggingFaceClient'
]