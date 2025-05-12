# -*- coding: utf-8 -*-
# /src/apis/huggingface_client.py

"""
Cliente API para HuggingFace Jobs.
Se especializa en recuperar ofertas de trabajo para roles de IA/ML y procesamiento de lenguaje natural.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import time
import random

from src.apis.base_api import BaseAPIClient
from src.utils.http_client import HTTPClient

logger = logging.getLogger(__name__)

class HuggingFaceClient(BaseAPIClient):
    """
    Cliente para obtener ofertas de empleo desde HuggingFace Jobs.
    HuggingFace se especializa en roles de IA, ML, y NLP.
    """
    
    def __init__(self, http_client: HTTPClient, config: Optional[Dict[str, Any]] = None):
        """
        Inicializa el cliente para HuggingFace Jobs.
        
        Args:
            http_client: Cliente HTTP para realizar peticiones
            config: Configuración específica para este cliente
        """
        super().__init__(source_name="huggingface", http_client=http_client, config=config)
        self.base_api_url = config.get('base_api_url', 'https://huggingface.co/api/jobs')
        logger.info(f"[{self.source_name}] Cliente API inicializado. Endpoint: {self.base_api_url}")
        
        # Headers personalizados para evitar bloqueos
        self.custom_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Origin': 'https://huggingface.co',
            'Referer': 'https://huggingface.co/jobs',
        }
    
    def _parse_api_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Parsea fechas de la API de HuggingFace al formato estándar YYYY-MM-DD.
        
        Args:
            date_str: String de fecha desde la API
            
        Returns:
            Fecha formateada en YYYY-MM-DD o None si hay error
        """
        if not date_str:
            return None
            
        try:
            # HuggingFace usa formato ISO en sus API
            dt_object = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt_object.strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"[{self.source_name}] Error al parsear fecha: {date_str} - {e}")
            return None
            
    def _normalize_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normaliza un trabajo de HuggingFace al formato estándar del sistema.
        
        Args:
            job_data: Datos crudos del trabajo desde la API
            
        Returns:
            Diccionario normalizado o None si no se puede procesar
        """
        if not job_data or not isinstance(job_data, dict):
            return None
            
        # Crear diccionario estándar
        oferta = self.get_standard_job_dict()
        
        # Extraer datos básicos
        oferta['titulo'] = job_data.get('title')
        oferta['empresa'] = job_data.get('company', {}).get('name') if job_data.get('company') else 'HuggingFace'
        
        # Ubicación (puede ser remoto o específico)
        location_data = job_data.get('location', {})
        is_remote = job_data.get('remote', False)
        
        if location_data and isinstance(location_data, dict) and 'text' in location_data:
            oferta['ubicacion'] = location_data['text']
        elif is_remote:
            oferta['ubicacion'] = 'Remote'
        else:
            oferta['ubicacion'] = 'No especificada'
            
        # URL
        job_id = job_data.get('id')
        if job_id:
            oferta['url'] = f"https://huggingface.co/jobs/{job_id}"
            
        # Fecha de publicación
        created_at = job_data.get('createdAt')
        oferta['fecha_publicacion'] = self._parse_api_date(created_at)
        
        # Descripción y metadatos
        description_parts = []
        
        # Obtener descripción principal
        if job_data.get('description'):
            description_parts.append(job_data['description'])
            
        # Obtener detalles adicionales
        details = job_data.get('details', {})
        if details and isinstance(details, dict):
            for key, value in details.items():
                if value and key not in ['description']:  # Evitar duplicar la descripción
                    formatted_key = key.replace('_', ' ').title()
                    description_parts.append(f"{formatted_key}: {value}")
                    
        # Obtener tags/skills
        tags = job_data.get('tags', [])
        if tags and isinstance(tags, list):
            description_parts.append(f"Skills/Tags: {', '.join(tags)}")
            
        # Obtener información salarial
        salary_data = job_data.get('salary', {})
        if salary_data and isinstance(salary_data, dict):
            min_salary = salary_data.get('min')
            max_salary = salary_data.get('max')
            currency = salary_data.get('currency', 'USD')
            
            if min_salary and max_salary:
                oferta['salario'] = f"{currency} {min_salary}-{max_salary}"
                description_parts.append(f"Salary: {oferta['salario']}")
                
        # Unir todas las partes de la descripción
        oferta['descripcion'] = "\n\n".join(description_parts)
        
        # Asegurar que tengamos datos mínimos
        if oferta['titulo'] and oferta['url']:
            oferta['fuente'] = self.source_name
            return oferta
            
        logger.warning(f"[{self.source_name}] Oferta omitida: falta título o URL. ID: {job_data.get('id', 'N/A')}")
        return None
        
    def fetch_jobs(self, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Obtiene ofertas de trabajo de HuggingFace Jobs en base a los parámetros proporcionados.
        
        Args:
            search_params: Diccionario con parámetros de búsqueda (keywords, location)
            
        Returns:
            Lista de ofertas de trabajo normalizadas
        """
        logger.info(f"[{self.source_name}] Consultando API de HuggingFace Jobs con parámetros: {search_params}")
        all_job_offers = []
        
        # Preparar parámetros de consulta
        query_params = {}
        
        # Añadir keywords (filtrar para enfocarse en datos y ML)
        keywords = search_params.get('keywords', [])
        if keywords:
            # Filtrar keywords relacionadas con datos/ML
            ml_data_keywords = [kw for kw in keywords if any(term in kw.lower() for term in 
                ['data', 'machine', 'learning', 'ml', 'ai', 'deep', 'neural', 'nlp', 
                 'python', 'pytorch', 'tensorflow', 'scientist', 'analyst'])]
                 
            # Si hay keywords específicas de ML/datos, usarlas; de lo contrario, usar las genéricas
            search_terms = ml_data_keywords if ml_data_keywords else keywords[:3]
            query_params['search'] = " ".join(search_terms)
        
        # Añadir ubicación (si es relevante)
        location = search_params.get('location', '')
        if location and not any(term in location.lower() for term in ['remote', 'remoto', 'teletrabajo']):
            query_params['location'] = location
        
        # Añadir filtro de remoto si se especifica en la ubicación
        if location and any(term in location.lower() for term in ['remote', 'remoto', 'teletrabajo']):
            query_params['remote'] = 'true'
        
        # Hacer la petición a la API
        try:
            response = self.http_client.get(
                self.base_api_url, 
                params=query_params,
                headers=self.custom_headers
            )
            
            if not response or response.status_code != 200:
                logger.error(f"[{self.source_name}] Error en la API. Status: {response.status_code if response else 'N/A'}")
                return []
                
            try:
                # Parsear respuesta JSON
                data = response.json()
                
                # Verificar estructura de datos
                if not isinstance(data, list):
                    logger.error(f"[{self.source_name}] Formato inesperado de respuesta. Se esperaba una lista.")
                    return []
                    
                # Procesar cada oferta
                for job_item in data:
                    # Añadir pequeña pausa aleatoria para evitar sobrecarga
                    time.sleep(random.uniform(0.1, 0.3))
                    
                    # Normalizar y añadir oferta
                    normalized_job = self._normalize_job(job_item)
                    if normalized_job:
                        all_job_offers.append(normalized_job)
                        
            except json.JSONDecodeError as e:
                logger.error(f"[{self.source_name}] Error al decodificar JSON: {e}")
            except Exception as e:
                logger.exception(f"[{self.source_name}] Error inesperado procesando resultados: {e}")
                
        except Exception as e:
            logger.exception(f"[{self.source_name}] Error al consultar API: {e}")
            
        logger.info(f"[{self.source_name}] {len(all_job_offers)} ofertas obtenidas y normalizadas.")
        return all_job_offers


if __name__ == '__main__':
    from src.utils.logging_config import setup_logging
    from src.utils.http_client import HTTPClient
    import pprint
    
    # Configurar logging
    setup_logging()
    
    # Crear cliente HTTP
    http_client = HTTPClient()
    
    # Configuración para el cliente API
    config = {
        'enabled': True,
        'base_api_url': 'https://huggingface.co/api/jobs'
    }
    
    # Crear instancia del cliente
    client = HuggingFaceClient(http_client=http_client, config=config)
    
    # Parámetros de búsqueda para probar
    search_params = {
        'keywords': ['machine learning', 'nlp', 'deep learning', 'python'],
        'location': 'Remote'
    }
    
    print(f"\n--- Iniciando prueba de {client.source_name} ---")
    print(f"Buscando trabajos con: {search_params}")
    
    try:
        # Ejecutar búsqueda
        ofertas = client.fetch_jobs(search_params)
        
        # Mostrar resultados
        print(f"\n--- Se encontraron {len(ofertas)} ofertas ---")
        
        if ofertas:
            print("\nPrimera oferta encontrada:")
            pprint.pprint(ofertas[0])
            
            print("\nÚltima oferta encontrada:")
            pprint.pprint(ofertas[-1])
            
    except Exception as e:
        print(f"Error durante la ejecución: {e}")
    finally:
        # Cerrar cliente HTTP
        http_client.close()
        print("\n--- Prueba finalizada ---")
