# Fase 3 — Normalización y mapeo GIS → modelo eléctrico canónico

## Objetivo

Transformar las capas crudas contenidas en `GisDataset` a `NetworkModel` sin acoplar
el dominio eléctrico a GeoPandas, PostGIS ni a DIgSILENT PowerFactory.

## Flujo implementado

```text
GIS Reader (Fase 2)
        ↓
    GisDataset
        ↓
  target_crs opcional
        ↓
RowAccessor + mapping.yaml
        ↓
normalización de IDs/unidades/estados
        ↓
GisToDomainMapper
        ↓
    NetworkModel
        ↓
Topología / validación
```

## Archivos de producción

### `src/gis2dgs/gis/normalizer.py`

Responsable de conversiones puras:

- identificadores obligatorios y opcionales;
- nombres con fallback;
- números, incluido decimal con coma simple;
- estados de interruptor;
- estados en/fuera de servicio;
- V → kV;
- m → km;
- W/kW → MW;
- var/kvar → Mvar;
- VA/kVA → MVA.

### `src/gis2dgs/gis/mapping/accessor.py`

Resuelve el campo lógico del dominio contra la columna real del GIS. Implementa:

- campos configurados;
- valores por defecto;
- detección de columnas inexistentes;
- campos obligatorios;
- contexto de error con capa, fila y campo.

### `src/gis2dgs/gis/mapping/domain_mapper.py`

Construye:

- `Bus`;
- `Line`;
- `Transformer`;
- `Switch`;
- `Load`;
- `Source`;
- `Substation`.

No contiene nombres DGS. El paso `NetworkModel → DGS` continúa separado.

### `src/gis2dgs/config/models.py`

El contrato de configuración admite por capa:

- `source`;
- `fields`;
- `units`;
- `defaults`.

También admite un `target_crs` opcional a nivel global.

### `config/mapping.yaml`

Ejemplo mantenible para adaptar los nombres reales de las capas y columnas GIS sin
modificar el código Python.

## Coordenadas

La prioridad implementada es:

1. campos `x` y `y` si ambos están configurados;
2. geometría `Point` de GeoPandas;
3. `None` si no existe información de punto.

No se calcula automáticamente longitud de línea desde geometría en esta fase, porque
hacerlo sin conocer el CRS y la calidad de la geometría puede introducir errores.
La longitud debe venir de un atributo GIS verificado o de una fase posterior explícita.

## Unidades canónicas del dominio

| Magnitud | Unidad interna |
|---|---|
| Tensión | kV |
| Longitud | km |
| Potencia activa | MW |
| Potencia reactiva | Mvar |
| Potencia aparente | MVA |

## Límites intencionales

La Fase 3 no:

- infiere conexiones eléctricas a partir de proximidad geométrica;
- crea objetos DGS;
- accede a la API de PowerFactory;
- corrige automáticamente topología eléctrica;
- inventa parámetros eléctricos ausentes.

Esas responsabilidades pertenecen a fases posteriores.
