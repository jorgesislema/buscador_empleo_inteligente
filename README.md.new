# Buscador de Empleo Inteligente

Sistema avanzado de búsqueda y agregación de ofertas de empleo a través de múltiples fuentes, incluyendo APIs y web scraping.

## Características Principales

- **Multi-fuente**: Consulta más de 15 portales de empleo diferentes
- **Procesamiento inteligente**: Normaliza y enriquece los datos de las ofertas
- **Filtrado avanzado**: Permite filtrar ofertas según múltiples criterios 
- **Exportación**: Guarda resultados en CSV y base de datos SQLite
- **Robusto**: Manejo avanzado de errores y estrategias anti-bloqueo
- **Escalable**: Arquitectura modular fácil de extender

## Versiones Disponibles

El sistema ofrece tres niveles de implementación con diferentes características:

1. **Pipeline Original** (`src/main.py`): Implementación básica
2. **Pipeline Mejorado** (`src/main_improved.py`): Con mejor manejo de errores y paralelismo
3. **Super Pipeline** (`src/super_pipeline.py`): Versión completa con todas las mejoras

## Mejoras Implementadas

El sistema ha sido mejorado con:

- **Cliente HTTP robusto**: Manejo avanzado de errores, rotación de User-Agents, reintentos inteligentes
- **Scrapers mejorados**: Versiones optimizadas para LinkedIn, InfoJobs y Computrabajo
- **APIs mejoradas**: Cliente de Adzuna con soporte multi-país y credenciales rotativas
- **Manejo centralizado de errores**: Sistema para registrar, analizar y recuperarse de fallos
- **Paralelismo adaptativo**: Estrategias optimizadas según el tipo de fuente

Consulta [MEJORAS.md](MEJORAS.md) para más detalles sobre las mejoras implementadas.

## Uso Rápido

### Instalación

```bash
# Clonar el repositorio
git clone https://github.com/tu-usuario/buscador_empleo_inteligente.git
cd buscador_empleo_inteligente

# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### Configuración

Edita el archivo `config/settings.yaml` para configurar:
- Parámetros de búsqueda (query, ubicación, etc.)
- Fuentes a utilizar
- Filtros a aplicar

### Ejecución

```bash
# Usar la versión más básica
python -m src.main

# Usar la versión mejorada
python -m src.main_improved

# Usar la versión con todas las mejoras
python -m src.super_pipeline

# Comparar rendimiento entre versiones
python scripts/run_super_scraper.py
```

## Estructura del Proyecto

```
buscador_empleo_inteligente/
├── config/                 # Configuración
├── data/                   # Datos y resultados
│   └── historico/          # Historial de búsquedas
├── docs/                   # Documentación
├── logs/                   # Registros de ejecución
├── scripts/                # Scripts útiles
├── src/                    # Código fuente
│   ├── apis/               # Clientes de API
│   ├── core/               # Lógica principal
│   ├── persistence/        # Almacenamiento
│   ├── scrapers/           # Web scrapers
│   └── utils/              # Utilidades
└── tests/                  # Pruebas
```

## Documentación

Para información más detallada, consulta:
- [Documentación técnica](docs/README_TECNICO.md)
- [Guía de uso](docs/USO.md)
- [Lista de mejoras](MEJORAS.md)

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.
