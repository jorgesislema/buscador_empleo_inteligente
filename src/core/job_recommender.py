# -*- coding: utf-8 -*-
# /src/core/job_recommender.py

"""
Sistema de recomendación de ofertas de empleo.

Este módulo implementa un sistema de recomendación que analiza
las descripciones de trabajo y las habilidades del usuario para
sugerir las ofertas más relevantes.
"""

import re
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
import sys

# Configuración de rutas para importaciones
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils import config_loader

logger = logging.getLogger(__name__)

class JobRecommender:
    """
    Sistema de recomendación para ofertas de trabajo.
    
    Analiza las ofertas de trabajo para extraer habilidades técnicas,
    tecnologías y requisitos, y los compara con el perfil del usuario
    para generar recomendaciones personalizadas.
    """
    
    def __init__(self):
        """Inicializa el sistema de recomendación."""
        logger.info("Inicializando JobRecommender...")
        try:
            # Cargamos la configuración y obtenemos la ruta a la BD
            config = config_loader.get_config()
            db_config = config.get('data_storage', {}).get('sqlite', {})
            db_filename = db_config.get('database_name', 'jobs.db')
            self.table_name = db_config.get('table_name', 'jobs')
            
            # Ruta a la BD
            self.db_path = config_loader.PROJECT_ROOT / "data" / db_filename
            logger.info(f"Utilizando base de datos: {self.db_path}")
            
            # Cargar lista de habilidades conocidas
            self.skills_data = self._load_skills()
            logger.info(f"Cargadas {len(self.skills_data['technical'])} habilidades técnicas y {len(self.skills_data['soft'])} habilidades blandas")
            
        except Exception as e:
            logger.exception(f"Error al inicializar JobRecommender: {e}")
            raise e
    
    def _load_skills(self) -> Dict[str, List[str]]:
        """
        Carga la lista de habilidades desde la configuración o usa valores predeterminados.
        
        Returns:
            Diccionario con listas de habilidades técnicas y blandas
        """
        # Intentamos cargar de la configuración
        config = config_loader.get_config()
        skills_config = config.get('skills', {})
        
        # Si no hay config o está vacía, usamos listas predeterminadas
        skills_data = {
            "technical": skills_config.get('technical', [
                # Lenguajes de programación
                "python", "java", "javascript", "typescript", "c#", "c++", "go", "rust", "php", "ruby", "swift", "kotlin",
                # Frontend
                "html", "css", "react", "angular", "vue", "svelte", "jquery", "bootstrap", "tailwind",
                # Backend
                "node.js", "django", "flask", "spring", "express", "fastapi", "laravel", "rails", 
                # Bases de datos
                "sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch", "sqlite", "oracle", "sql server",
                # Cloud y DevOps
                "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "jenkins", "github actions", "gitlab ci",
                # Ciencia de datos y ML
                "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "machine learning", "data science",
                "big data", "data engineering", "data analysis", "power bi", "tableau", "etl",
                # Móvil
                "android", "ios", "flutter", "react native", "xamarin", 
                # Otros
                "git", "rest", "graphql", "microservices", "agile", "scrum", "jira"
            ]),
            "soft": skills_config.get('soft', [
                "comunicación", "trabajo en equipo", "liderazgo", "resolución de problemas", 
                "pensamiento crítico", "creatividad", "gestión del tiempo", "adaptabilidad",
                "empatía", "negociación", "presentación", "mentoría", "compromiso"
            ])
        }
        
        return skills_data
    
    def extract_skills(self, text: str) -> Tuple[Set[str], Set[str]]:
        """
        Extrae habilidades técnicas y blandas de un texto.
        
        Args:
            text: Texto para analizar
            
        Returns:
            Tupla con dos conjuntos: (habilidades técnicas, habilidades blandas)
        """
        if not text:
            return set(), set()
        
        text = text.lower()
        technical_skills = set()
        soft_skills = set()
        
        # Buscar habilidades técnicas
        for skill in self.skills_data['technical']:
            # Buscar como palabra completa
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text):
                technical_skills.add(skill)
        
        # Buscar habilidades blandas
        for skill in self.skills_data['soft']:
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text):
                soft_skills.add(skill)
        
        return technical_skills, soft_skills
    
    def recommend_jobs(self, user_skills: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Recomienda trabajos basados en las habilidades del usuario.
        
        Args:
            user_skills: Lista de habilidades del usuario
            limit: Número máximo de recomendaciones
            
        Returns:
            Lista de trabajos recomendados con puntuación de coincidencia
        """
        logger.info(f"Generando recomendaciones para {len(user_skills)} habilidades")
        
        if not user_skills:
            logger.warning("Lista de habilidades vacía")
            return []
        
        # Normalizar habilidades del usuario a minúsculas
        user_skills_set = set(skill.lower() for skill in user_skills)
        
        try:
            # Obtener trabajos recientes
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = self._dict_factory
                cursor = conn.cursor()
                
                # Obtener trabajos recientes
                cursor.execute(f'''
                SELECT * FROM {self.table_name} 
                ORDER BY fecha_insercion DESC 
                LIMIT 1000
                ''')
                
                all_jobs = cursor.fetchall()
                logger.info(f"Analizando {len(all_jobs)} ofertas recientes")
                
                # Calcular coincidencias
                job_matches = []
                
                for job in all_jobs:
                    # Extraer habilidades del título y descripción
                    title_text = job.get('titulo', '') or ''
                    desc_text = job.get('descripcion', '') or ''
                    combined_text = f"{title_text} {desc_text}"
                    
                    # Extraer habilidades del texto combinado
                    tech_skills, soft_skills = self.extract_skills(combined_text)
                    
                    # Calcular coincidencia
                    tech_match = len(tech_skills.intersection(user_skills_set))
                    soft_match = len(soft_skills.intersection(user_skills_set))
                    
                    # Peso: Las coincidencias en habilidades técnicas valen más
                    match_score = (tech_match * 3) + soft_match
                    
                    # Añadir a resultados si hay alguna coincidencia
                    if match_score > 0:
                        # Convertir las habilidades coincidentes a una lista
                        matching_skills = list(tech_skills.union(soft_skills).intersection(user_skills_set))
                        
                        job_matches.append({
                            'job': job,
                            'score': match_score,
                            'matching_skills': matching_skills,
                            'total_skills_found': len(tech_skills) + len(soft_skills)
                        })
                
                # Ordenar por puntuación de coincidencia
                job_matches.sort(key=lambda x: x['score'], reverse=True)
                
                logger.info(f"Encontradas {len(job_matches)} ofertas con coincidencia")
                
                # Formatear resultados para devolver
                result = []
                for match in job_matches[:limit]:
                    job_data = match['job']
                    result.append({
                        'id': job_data.get('id'),
                        'titulo': job_data.get('titulo'),
                        'empresa': job_data.get('empresa'),
                        'ubicacion': job_data.get('ubicacion'),
                        'url': job_data.get('url'),
                        'fuente': job_data.get('fuente'),
                        'fecha_publicacion': job_data.get('fecha_publicacion'),
                        'score': match['score'],
                        'matching_skills': match['matching_skills'],
                        'total_skills_found': match['total_skills_found']
                    })
                
                return result
                
        except sqlite3.Error as e:
            logger.exception(f"Error al obtener recomendaciones: {e}")
            return []
    
    def _dict_factory(self, cursor, row):
        """Convierte filas de SQLite a diccionarios."""
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

# Ejemplo de uso (si se ejecuta directamente)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, 
                        format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
    
    print("--- Probando JobRecommender ---")
    try:
        recommender = JobRecommender()
        
        # Realizar recomendaciones de prueba
        user_profiles = [
            ["python", "django", "sql", "react", "git"],
            ["java", "spring", "javascript", "docker", "aws"],
            ["data science", "machine learning", "python", "pandas", "tableau"],
            ["javascript", "typescript", "node.js", "react", "mongodb"]
        ]
        
        for i, skills in enumerate(user_profiles, 1):
            print(f"\nPerfil {i}: {', '.join(skills)}")
            recommendations = recommender.recommend_jobs(skills, limit=3)
            
            print(f"Se encontraron {len(recommendations)} recomendaciones:")
            for j, rec in enumerate(recommendations, 1):
                print(f"{j}. {rec['titulo']} - {rec['empresa']}")
                print(f"   Ubicación: {rec['ubicacion']}")
                print(f"   Puntuación: {rec['score']}")
                print(f"   Habilidades coincidentes: {', '.join(rec['matching_skills'])}")
                print(f"   URL: {rec['url']}")
                print()
                
    except Exception as e:
        print(f"Error: {e}")