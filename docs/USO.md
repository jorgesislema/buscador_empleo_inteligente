# Guía de Uso - Buscador de Empleo Inteligente

Esta guía explica cómo utilizar el Buscador de Empleo Inteligente para obtener ofertas de trabajo de múltiples fuentes.

## Requisitos Previos

- Python 3.8 o superior
- Pip (gestor de paquetes de Python)
- Git (opcional, para clonar el repositorio)

## Instalación

### 1. Obtener el Código

Clona el repositorio (si tienes Git):

```bash
git clone https://github.com/tu-usuario/buscador_empleo_inteligente.git
cd buscador_empleo_inteligente
```

O descarga y descomprime el archivo ZIP.

### 2. Crear Entorno Virtual (Recomendado)

En Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

En macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

## Configuración

La configuración se realiza en el archivo `config/settings.yaml`. Este archivo contiene:

### 1. Parámetros de Búsqueda

```yaml
search_params:
  query: "python developer"    # Palabras clave de búsqueda
  location: "Madrid"           # Ubicación
  max_results: 100             # Máximo de resultados por fuente
  max_pages: 10                # Máximo de páginas a consultar
  max_days_old: 30             # Antigüedad máxima de las ofertas
```

### 2. Fuentes de Datos

Activa o desactiva fuentes específicas:

```yaml
sources:
  linkedin: true
  infojobs: true
  computrabajo: true
  adzuna: true
  jooble: true
  # ... otras fuentes
```

### 3. Filtros

```yaml
filters:
  keywords_include:            # Palabras que deben aparecer
    - "python"
    - "django"
  keywords_exclude:            # Palabras que NO deben aparecer
    - "php"
    - "wordpress"
  min_salary: 25000            # Salario mínimo anual
  job_types:                   # Tipos de trabajo
    - "remote"
    - "hybrid"
```

## Ejecución

### Pipeline Básico

```bash
python -m src.main
```

### Pipeline Mejorado

Con mejor manejo de errores y paralelismo:

```bash
python -m src.main_improved
```

### Super Pipeline (Todas las Mejoras)

Con todas las optimizaciones:

```bash
python -m src.super_pipeline
```

### Comparar Rendimiento

Para ejecutar todas las versiones y comparar resultados:

```bash
python scripts/run_super_scraper.py
```

Con parámetros personalizados:

```bash
python scripts/run_super_scraper.py --query "data engineer" --location "Barcelona"
```

## Resultados

Los resultados se guardan en varios formatos:

### 1. Base de Datos

Ruta: `data/jobs.db`

Puedes consultarla con SQLite:
```bash
sqlite3 data/jobs.db "SELECT title, company, location FROM jobs LIMIT 10"
```

### 2. Archivos CSV

Se generan varios archivos CSV:

- `data/historico/ofertas_filtradas_YYYY-MM-DD.csv`: Ofertas filtradas de la ejecución actual
- `data/historico/ofertas_todas_YYYY-MM-DD.csv`: Todas las ofertas sin filtrar

### 3. Estadísticas

En la carpeta `data/stats` encontrarás archivos JSON con estadísticas detalladas de cada ejecución.

## Funcionalidades Avanzadas

### 1. Procesamiento por Lotes

Para procesamiento de grandes volúmenes:

```bash
python scripts/run_scraper_manualmente.py --batch 5000
```

### 2. Ejecución Programada

Configura ejecuciones periódicas:

```bash
python scripts/run_scheduler.py
```

### 3. Exportación Personalizada

Puedes exportar resultados en diferentes formatos:

```bash
python scripts/export_jobs.py --format json --days 7
```

## Solución de Problemas

### Errores Comunes

1. **"No se pudieron importar módulos esenciales"**
   - Asegúrate de estar ejecutando desde la carpeta raíz del proyecto
   - Verifica que los archivos `__init__.py` estén presentes en cada carpeta

2. **"Error en fuente X: Connection Error"**
   - Puede ser un problema temporal de conectividad
   - Prueba ejecutando solo esa fuente: `python -m src.main --only linkedin`

3. **"SSL Certificate Error"**
   - Problema con certificados SSL en algunos sitios
   - Usa la versión mejorada que maneja estos errores: `python -m src.main_improved`

### Logs

Revisa los logs para más detalles sobre errores:
```
logs/app.log
```

## Recomendaciones

- **Empieza Pequeño**: Para pruebas, configura pocas fuentes y limita los resultados
- **Fuentes Confiables**: LinkedIn, InfoJobs y Adzuna suelen ser las más fiables
- **Evita Sobrecarga**: No ejecutes el scraper demasiado frecuentemente para evitar bloqueos
- **VPN**: Para uso intensivo, considera utilizar una VPN

## Próximos Pasos

Después de dominar el uso básico:

1. Personaliza los filtros para tu búsqueda de empleo específica
2. Implementa tu propio scraper para sitios adicionales
3. Configura ejecuciones automáticas con el planificador
4. Explora los datos con herramientas de análisis

Para más información técnica, consulta la [documentación técnica](README_TECNICO.md).