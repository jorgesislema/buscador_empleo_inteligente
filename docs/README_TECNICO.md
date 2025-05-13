# Documentación Técnica - Buscador de Empleo Inteligente

## Arquitectura del Sistema

El Buscador de Empleo Inteligente está diseñado con una arquitectura modular orientada a objetos que facilita su mantenimiento y extensión. La estructura general sigue un patrón de capas:

1. **Capa de Entrada/Salida**: Manejo de configuración, logs y exportación de resultados
2. **Capa de Fuentes**: APIs y scrapers para obtener datos de diferentes portales
3. **Capa de Procesamiento**: Normalización y enriquecimiento de datos
4. **Capa de Filtrado**: Aplicación de filtros configurables
5. **Capa de Persistencia**: Almacenamiento en base de datos y exportación

### Diagrama de Componentes

```
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│  Fuentes   │───▶│Procesamiento│───▶│  Filtrado  │───▶│Persistencia│
└────────────┘    └────────────┘    └────────────┘    └────────────┘
       ▲                                                    │
       │           ┌─────────────────────────────┐         │
       └───────────│     Configuración/Logs      │◀────────┘
                   └─────────────────────────────┘
```

## Principales Componentes

### 1. Scrapers

Los scrapers son clases que heredan de `BaseScraper` e implementan la lógica para extraer datos de sitios web de empleo:

- `LinkedInScraper`: Extrae ofertas de LinkedIn
- `InfojobsScraper`: Extrae ofertas de InfoJobs
- `ComputrabajoScraper`: Extrae ofertas de Computrabajo
- Y muchos más...

#### Versiones Mejoradas

Las versiones mejoradas (con sufijo `_improved`) añaden características avanzadas:

- Procesamiento de páginas de detalle
- Estrategias anti-bloqueo (rotación de User-Agents, delays aleatorios)
- Reintentos inteligentes en caso de fallos
- Mejor extracción de datos (múltiples selectores)

### 2. Clientes API

Los clientes API heredan de `BaseAPIClient` e implementan la conexión con APIs de empleo:

- `AdzunaClient`: API de Adzuna
- `JoobleClient`: API de Jooble
- `RemoteOkClient`: API de RemoteOK
- Y otros...

#### Versiones Mejoradas

Las versiones mejoradas añaden:

- Soporte multi-país
- Rotación de credenciales
- Estrategias de variación de parámetros
- Manejo avanzado de errores

### 3. Procesamiento de Datos

La clase `data_processor` se encarga de:

- Normalizar campos (fechas, salarios, ubicaciones)
- Enriquecer los datos (detección de modalidad, nivel, tecnologías)
- Deduplicar ofertas

### 4. Filtrado

La clase `JobFilter` aplica filtros configurables:

- Por palabras clave
- Por ubicación
- Por salario
- Por modalidad
- Por antigüedad
- Etc.

### 5. Persistencia

El sistema incluye dos mecanismos de persistencia:

- `DatabaseManager`: Guarda en SQLite
- `file_exporter`: Exporta a CSV

## Niveles de Implementación

El sistema ofrece tres niveles de implementación:

### 1. Pipeline Original (`main.py`)

Implementación básica con:
- Procesamiento secuencial
- Manejo básico de errores
- Sin optimizaciones especiales

### 2. Pipeline Mejorado (`main_improved.py`)

Mejoras enfocadas en robustez:
- Manejo avanzado de errores
- Paralelismo básico
- Reintentos para fuentes fallidas

### 3. Super Pipeline (`super_pipeline.py`)

Implementación completa con todas las mejoras:
- Detección automática de componentes mejorados
- Paralelismo adaptativo (diferentes estrategias según tipo de fuente)
- Sistema de estadísticas detallado
- Estrategias de búsqueda optimizadas

## Utilidades Avanzadas

### HTTP Client Mejorado

La clase `ImprovedHTTPClient` proporciona:

- Rotación de User-Agents
- Manejo avanzado de errores HTTP/SSL
- Reintentos con backoff exponencial
- Estadísticas de peticiones
- Headers personalizados según dominio

### Error Handler

El módulo `error_handler` ofrece:

- Registro centralizado de errores
- Análisis de patrones de fallos
- Generación de estrategias alternativas
- Reintentos inteligentes

## Extensibilidad

Para añadir nuevas fuentes:

1. **APIs**: Crear una nueva clase que herede de `BaseAPIClient`
2. **Scrapers**: Crear una nueva clase que herede de `BaseScraper`
3. **Registrar** la nueva fuente en `SOURCE_MAP` en el pipeline correspondiente
4. **Activar** la fuente en `settings.yaml`

## Optimización de Rendimiento

El Super Pipeline implementa varias optimizaciones:

- **Paralelismo inteligente**: Las APIs se ejecutan en paralelo mientras que los scrapers se ejecutan en bloques pequeños con pausas
- **Búsqueda robusta**: Variación automática de parámetros para maximizar resultados
- **Reintentos adaptativos**: Backoff exponencial con jitter para evitar bloqueos
- **Detección automática de mejoras**: Uso automático de versiones mejoradas cuando están disponibles

## Notas de Implementación

- Las mejoras son compatibles con el sistema original
- El sistema detecta automáticamente los módulos mejorados disponibles
- Los componentes utilizan inyección de dependencias para facilitar pruebas
- El sistema es configurado a través de `settings.yaml`