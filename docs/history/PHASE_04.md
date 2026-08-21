# Fase 4 — Motor topológico avanzado

## Objetivo

Convertir el `NetworkModel` canónico en una representación topológica eléctrica apta para:

1. tracing desde fuentes/SET;
2. separación de redes por interruptores abiertos;
3. identificación de islas energizadas y desenergizadas;
4. identificación de alimentadores desde elementos raíz;
5. límites de tensión mediante transformadores;
6. detección de mallas y elementos paralelos;
7. descomposición en ramales;
8. diagnóstico de superposición de alimentadores;
9. propuesta controlada de conexiones GIS faltantes mediante proximidad espacial.

La fase no modifica silenciosamente el `NetworkModel` ni corrige automáticamente el GIS.
Las correcciones espaciales se generan primero como propuestas auditables.

## Arquitectura

```text
GisDataset
    │
    ├── gis/connectivity.py
    │      ├── detectar extremos de LineString
    │      ├── buscar buses candidatos
    │      ├── detectar ambigüedad
    │      └── aplicar propuesta explícitamente
    │
    ▼
NetworkModel
    │
    └── topology/
           ├── graph.py
           ├── analysis.py
           ├── tracing.py
           ├── branches.py
           ├── models.py
           └── analyzer.py
                │
                ▼
          TopologyReport
```

## `topology/graph.py`

Se mantienen dos grafos deliberadamente diferentes.

### Grafo conductivo

`build_graph(network)` representa únicamente caminos eléctricos que conducen:

- líneas en servicio;
- interruptores en servicio y cerrados;
- transformadores en servicio.

Los interruptores abiertos no forman una arista conductiva.

Se usa `networkx.MultiGraph` para preservar líneas o equipos paralelos entre las mismas barras.

### Grafo físico

`build_physical_graph(network)` puede representar interruptores abiertos y equipos fuera de servicio
para diagnóstico. Cada arista contiene atributos `conductive` e `in_service`.

No debe utilizarse este grafo para determinar energización.

## `topology/analysis.py`

Implementa:

- `connected_components()`;
- `isolated_buses()`;
- `trace_from()`;
- `active_source_buses()`;
- `trace_sources()`;
- `energized_buses()`;
- `deenergized_buses()`;
- `find_islands()`;
- `find_cycles()`.

### Islas

Cada `TopologyIsland` contiene:

- buses;
- fuentes presentes;
- número de aristas;
- condición energizada/desenergizada;
- condición radial/mallada.

Una componente se considera radial cuando:

```text
E = N - 1
```

para una componente conectada, donde `E` es el número de aristas y `N` el número de buses.

## `topology/tracing.py`

### `TracePolicy`

Permite controlar el tracing:

```python
TracePolicy(
    cross_transformers=False,
    stop_at_other_sources=True,
)
```

Por defecto un alimentador no cruza transformadores. Esto mantiene el tracing dentro del nivel de
la fuente. Si se requiere un tracing multivoltaje puede activarse `cross_transformers=True`.

### Alimentadores

`trace_feeders()` parte de cada arista conductiva conectada a una fuente activa.

Para cada alimentador registra:

- fuente;
- barra de fuente;
- barra raíz;
- elemento raíz;
- etiqueta GIS `feeder_id` cuando existe;
- buses alcanzados;
- elementos alcanzados;
- buses límite;
- presencia de ciclo.

### Interruptores abiertos

`find_open_switch_boundaries()` conserva cada switch abierto como límite y determina si cada extremo
está energizado. Esto permite identificar, por ejemplo, una frontera entre una red energizada y una
zona desenergizada.

### Superposición de alimentadores

`find_feeder_overlaps()` detecta buses alcanzados por más de un tracing de alimentador. Esto puede
indicar:

- malla cerrada;
- tie cerrado;
- doble alimentación;
- error de modelado GIS;
- configuración intencional que debe revisarse antes de asumir radialidad.

No se corrige automáticamente.

## `topology/branches.py`

`extract_branches()` divide el grafo en caminos máximos entre puntos estructurales.

Se generan límites en:

- nodos terminales;
- derivaciones;
- nodos con elementos paralelos;
- interruptores;
- transformadores;
- buses definidos explícitamente como stop.

El algoritmo conserva todos los IDs de las aristas y también soporta componentes cíclicas sin
perder elementos.

## `topology/models.py`

Objetos inmutables de salida:

- `EdgeRef`;
- `TopologyIsland`;
- `SourceTrace`;
- `FeederTrace`;
- `BranchTrace`;
- `CycleTrace`;
- `OpenSwitchBoundary`;
- `FeederOverlap`;
- `TopologyReport`.

Estos modelos no dependen de PowerFactory ni del formato DGS.

## `topology/analyzer.py`

`TopologyAnalyzer` es la fachada de la fase:

```python
report = TopologyAnalyzer().analyze(network)
```

Devuelve un `TopologyReport` sin modificar `network`.

## Reconstrucción controlada de conectividad GIS

La proximidad geométrica pertenece a `gis/`, no a `topology/`, porque trabaja con geometrías y CRS.
Por ello se implementó en:

```text
src/gis2dgs/gis/connectivity.py
```

### Flujo

```text
LineString con from/to faltante o inválido
            ↓
extremo geométrico
            ↓
STRtree de buses Point
            ↓
candidatos dentro de tolerance_m
            ↓
único candidato más cercano → propuesta resuelta
empate geométrico             → propuesta ambigua
sin candidato                 → propuesta no resuelta
            ↓
apply_connection_proposal()
            ↓
GeoDataFrame nuevo
```

### Salvaguardas

La inferencia espacial exige:

- CRS proyectado;
- unidades métricas;
- mismo CRS en líneas y buses;
- geometrías `Point` para buses;
- geometrías `LineString` para líneas;
- IDs de bus únicos;
- tolerancia positiva.

No se utilizan grados geográficos como si fueran metros.

### No mutación

`propose_line_endpoint_connections()` no cambia la capa GIS.

`apply_connection_proposal()` devuelve una copia y aplica solamente resultados no ambiguos.

Esto separa diagnóstico y modificación.

## Límites intencionales

La Fase 4 no:

- modifica automáticamente el GIS original;
- decide que una superposición de alimentadores es un error;
- calcula parámetros eléctricos;
- genera DGS;
- crea `StaCubic` o terminales PowerFactory;
- ejecuta flujo de carga;
- sustituye las validaciones eléctricas ampliadas de la Fase 5.

## Validación ejecutada

La versión v0.4 se verificó con:

- 100 pruebas `pytest` aprobadas;
- 92 % de cobertura global;
- 100 % de cobertura de `topology/analyzer.py`;
- 95 % de `topology/analysis.py`;
- 95 % de `topology/branches.py`;
- 93 % de `topology/tracing.py`;
- compilación completa con `compileall`;
- importación correcta de 46 módulos;
- 0 líneas Python superiores a 100 caracteres;
- prueba de escala con 5 000 buses y 4 999 líneas: análisis completo en aproximadamente 0,21 s en
  el entorno de desarrollo utilizado.

Las cuatro advertencias observadas son `DeprecationWarning` emitidas por `pyproj` durante pruebas de
reproyección ya existentes; las pruebas finalizan correctamente.
