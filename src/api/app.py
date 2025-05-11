# /src/api/app.py

"""
API REST para el Buscador de Empleo Inteligente.

Este módulo implementa una API REST utilizando Flask para acceder
a los datos recopilados por el buscador de empleo.
"""

from flask import Flask, jsonify, request, abort
from flask import Flask, jsonify, request
import sqlite3
import logging
from pathlib import Path
import sys
import json

# Configuración de rutas para importaciones
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils import config_loader, logging_config
from src.persistence.database_manager import DatabaseManager
from src.main import run_job_search_pipeline
# Configuración de logging
logging_config.setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Habilitar CORS para todas las rutas

# Inicializar configuración
config = config_loader.get_config()
db_config = config.get('data_storage', {}).get('sqlite', {})
db_path = config_loader.PROJECT_ROOT / "data" / db_config.get('database_name', 'jobs.db')
table_name = db_config.get('table_name', 'jobs')

def dict_factory(cursor, row):
    """Convertir filas de SQLite a diccionarios."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint para verificar que la API está funcionando."""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "message": "Buscador de Empleo API está funcionando correctamente"
    })

@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    """Obtener listado de ofertas con filtros opcionales."""
    try:
        # Parámetros de consulta
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)  # Máximo 100 por página
        keyword = request.args.get('keyword', None)
        company = request.args.get('company', None)
        location = request.args.get('location', None)
        days = request.args.get('days', None)
        source = request.args.get('source', None)
        
        # Construir consulta SQL base
        query = f"SELECT * FROM {table_name} WHERE 1=1"
        params = []
        
        # Aplicar filtros si existen
        if keyword:
            query += " AND (titulo LIKE ? OR descripcion LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        
        if company:
            query += " AND empresa LIKE ?"
            params.append(f"%{company}%")
        
        if location:
            query += " AND ubicacion LIKE ?"
            params.append(f"%{location}%")
        
        if days:
            # Filtrar por fecha de inserción (últimos N días)
            days_ago = (datetime.now() - timedelta(days=int(days))).strftime('%Y-%m-%d')
            query += " AND fecha_insercion >= ?"
            params.append(days_ago)
        
        if source:
            query += " AND fuente = ?"
            params.append(source)
        
        # Añadir ordenamiento y paginación
        query += " ORDER BY fecha_insercion DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        # Ejecutar consulta
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            cursor.execute(query, params)
            jobs = cursor.fetchall()
            
            # Contar total de resultados (sin paginación)
            count_query = f"SELECT COUNT(*) as total FROM {table_name} WHERE 1=1"
            # Reusamos los parámetros pero quitamos los de paginación
            count_params = params[:-2] if len(params) >= 2 else params
            
            cursor.execute(count_query, count_params)
            total = cursor.fetchone()['total']
        
        # Construir respuesta paginada
        response = {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
            "jobs": jobs
        }
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error al obtener ofertas de trabajo: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/jobs/<int:job_id>', methods=['GET'])
def get_job_by_id(job_id):
    """Obtener una oferta de trabajo por su ID."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name} WHERE id = ?", (job_id,))
            job = cursor.fetchone()
            
            if not job:
                return jsonify({"error": "Oferta no encontrada"}), 404
            
            return jsonify(job)
    
    except Exception as e:
        logger.error(f"Error al obtener oferta ID {job_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Obtener estadísticas sobre las ofertas almacenadas."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            
            # Total de ofertas
            cursor.execute(f"SELECT COUNT(*) as total FROM {table_name}")
            total = cursor.fetchone()['total']
            
            # Ofertas por fuente
            cursor.execute(f"SELECT fuente, COUNT(*) as count FROM {table_name} GROUP BY fuente ORDER BY count DESC")
            sources = cursor.fetchall()
            
            # Ofertas por ubicación (top 10)
            cursor.execute(f"""
                SELECT ubicacion, COUNT(*) as count 
                FROM {table_name} 
                WHERE ubicacion IS NOT NULL AND ubicacion != '' 
                GROUP BY ubicacion 
                ORDER BY count DESC
                LIMIT 10
            """)
            locations = cursor.fetchall()
            
            # Ofertas por empresa (top 10)
            cursor.execute(f"""
                SELECT empresa, COUNT(*) as count 
                FROM {table_name} 
                WHERE empresa IS NOT NULL AND empresa != '' 
                GROUP BY empresa 
                ORDER BY count DESC
                LIMIT 10
            """)
            companies = cursor.fetchall()
            
            # Ofertas por día (últimos 30 días)
            cursor.execute(f"""
                SELECT DATE(fecha_insercion) as date, COUNT(*) as count 
                FROM {table_name} 
                WHERE fecha_insercion >= DATE('now', '-30 day')
                GROUP BY DATE(fecha_insercion) 
                ORDER BY date
            """)
            daily = cursor.fetchall()
            
            stats = {
                "total_jobs": total,
                "by_source": sources,
                "top_locations": locations,
                "top_companies": companies,
                "daily_trend": daily
            }
            
            return jsonify(stats)
    
    except Exception as e:
        logger.error(f"Error al obtener estadísticas: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/run-pipeline', methods=['POST'])
def trigger_pipeline():
    """Ejecutar el pipeline de búsqueda de empleo manualmente."""
    try:
        # Ejecutar pipeline en segundo plano (esto podría mejorarse con Celery o similar)
        # Por ahora, simplemente ejecutamos sincrónicamente
        run_job_search_pipeline()
        return jsonify({
            "status": "success",
            "message": "Pipeline ejecutado correctamente"
        })
    except Exception as e:
        logger.error(f"Error al ejecutar pipeline: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/search', methods=['GET'])
def search_jobs():
    """Búsqueda de texto completo en ofertas de trabajo."""
    try:
        from src.persistence.search_engine import JobSearchEngine
        
        # Parámetros de consulta
        query = request.args.get('q', '')
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 20)), 100)  # Máximo 100 por página
        
        if not query:
            return jsonify({"error": "El parámetro de búsqueda 'q' es requerido"}), 400
        
        # Inicializar motor de búsqueda
        search_engine = JobSearchEngine()
        
        # Realizar búsqueda
        offset = (page - 1) * per_page
        results = search_engine.search(query, limit=per_page, offset=offset)
        total = search_engine.get_total_results(query)
        
        # Construir respuesta paginada
        response = {
            "query": query,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page,
            "results": results
        }
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error en búsqueda FTS: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/recommendations', methods=['POST'])
def get_recommendations():
    """Obtener recomendaciones de trabajo basadas en habilidades."""
    try:
        from src.core.job_recommender import JobRecommender
        
        # Obtener datos de la solicitud
        request_data = request.get_json()
        if not request_data:
            return jsonify({"error": "Se requiere un objeto JSON con habilidades"}), 400
        
        # Obtener la lista de habilidades
        skills = request_data.get('skills', [])
        if not skills or not isinstance(skills, list):
            return jsonify({"error": "El campo 'skills' debe ser una lista no vacía"}), 400
        
        # Número de recomendaciones a devolver
        limit = min(int(request_data.get('limit', 10)), 50)  # Máximo 50 recomendaciones
        
        # Inicializar recomendador
        recommender = JobRecommender()
        
        # Obtener recomendaciones
        recommendations = recommender.recommend_jobs(skills, limit=limit)
        
        # Construir respuesta
        response = {
            "skills": skills,
            "count": len(recommendations),
            "recommendations": recommendations
        }
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error al obtener recomendaciones: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)