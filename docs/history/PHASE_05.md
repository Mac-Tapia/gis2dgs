# Fase 5 — Motor de validación

## Objetivo

Consolidar un motor de validación mantenible entre `NetworkModel`/`TopologyReport` y las futuras
fases de biblioteca eléctrica, mapping DGS e importación PowerFactory.

El motor no corrige datos automáticamente. Clasifica hallazgos, aplica perfiles explícitos y genera
reportes reproducibles para revisión.

## Carpetas y responsabilidades

### `src/gis2dgs/validation/`

- `policy.py`: perfiles y tolerancias configurables.
- `result.py`: severidad, categoría, issue y reporte.
- `network_rules.py`: integridad estructural y referencias.
- `data_quality_rules.py`: valores finitos y coordenadas canónicas.
- `electrical_rules.py`: coherencia de niveles de tensión.
- `topology_rules.py`: islas, buses sin energía, ciclos, overlaps y fronteras abiertas.
- `readiness_rules.py`: requisitos dependientes del perfil antes de análisis/importación.
- `validator.py`: orquestación; calcula `TopologyReport` una sola vez.
- `exporters.py`: salida JSON/CSV en formato estable.

### `src/gis2dgs/config/validation.py`

Carga `config/validation.yaml` y construye `ValidationPolicy`. La interpretación de configuración
permanece fuera del dominio eléctrico.

## Perfiles

### `standard`

Validación canónica general. No exige tipos eléctricos ni coordenadas geográficas.

### `power_flow`

Exige:

- al menos una fuente en servicio;
- `type_id` en líneas en servicio;
- `type_id` en transformadores en servicio;
- todas las barras alcanzables desde una fuente.

La Fase 5 valida la **presencia** de la referencia de tipo. La existencia y parámetros del tipo se
validarán contra la biblioteca eléctrica en la Fase 6.

### `geographic`

Exige coordenadas x/y en buses y subestaciones para preparar representación geográfica.

### `radial_distribution`

Exige fuente, energización total, radialidad y ausencia de solapamiento de alimentadores.

## Catálogo inicial de códigos

- `NET001`–`NET005`: referencia a barra inexistente.
- `NET006`: red sin barras.
- `DAT001`: valor numérico no finito.
- `DAT002`: par de coordenadas incompleto.
- `DAT003`: coordenadas requeridas ausentes.
- `ELE001`–`ELE005`: incoherencias de tensión.
- `TOP001`: barra aislada.
- `TOP002`: barra no alcanzable desde fuente.
- `TOP003`: ciclo simple.
- `TOP004`: elementos paralelos.
- `TOP005`: solapamiento de trazas de alimentador.
- `TOP006`: isla con múltiples fuentes.
- `TOP007`: switch abierto entre lado energizado y desenergizado.
- `RDY001`: falta fuente exigida por perfil.
- `RDY002`: línea sin tipo exigido.
- `RDY003`: transformador sin tipo exigido.
- `RDY004`: barra desenergizada no permitida.
- `RDY005`: red no radial bajo perfil radial.
- `RDY006`: overlap de feeder no permitido.

## Principios de mantenimiento

1. Las reglas no modifican `NetworkModel`.
2. `validation/` no depende de GeoPandas ni de PowerFactory.
3. Las reglas universales y las reglas dependientes de perfil están separadas.
4. La topología se calcula una vez por validación.
5. Los reportes se ordenan de forma determinista.
6. Los requisitos específicos del DGS exacto continúan diferidos hasta disponer del DGS patrón.
