# Arquitectura GIS2DGS 1.0.0

## Principios

1. **Origen neutral**: el núcleo no conoce ArcGIS, IGEA, QGIS ni otra marca.
2. **Adapters at the edge**: archivos y DB se convierten primero a `InputDataset`.
3. **Mapping externo**: nombres de tablas/columnas se resuelven por YAML.
4. **Dominio independiente**: `domain/` no depende de GeoPandas, SQLAlchemy ni DGS.
5. **Topología explícita**: la conectividad eléctrica se analiza como multigrafo.
6. **Validación antes de serializar**: el DGS no se genera si la política exige
   ausencia de errores y la red no cumple.
7. **DGS schema-driven**: la compatibilidad se verifica por estructura DGS, no por
   una versión de PowerFactory.
8. **Dependencias opcionales**: drivers DB/Parquet/XLS heredado no inflan el core.
9. **Configuración separada de datos técnicos**: biblioteca eléctrica y mappings
   se pueden mantener por empresa/proyecto sin tocar el código.
10. **Determinismo**: foreign keys PowerFactory se generan de forma estable.

## Capas

```text
input/                  lectores, detección, schema discovery, merge
  ↓
gis/                    geometría/CRS/conectividad espacial y mapper legado
  ↓
domain/                 modelo eléctrico canónico
  ↓
topology/               multigrafo, tracing, islas, ciclos y feeders
  ↓
electrical/             biblioteca de tipos
  ↓
validation/             reglas y reportes
  ↓
powerfactory/           modelo semántico node-breaker
  ↓
dgs/                    schema, mapper, validator, template inspector, writer
  ↓
cli/ + pipeline.py       orquestación ejecutable
```

## Extensibilidad

Un nuevo esquema de empresa requiere un YAML distinto. Un nuevo formato físico
se agrega como un reader en `input/readers/` y se registra en la factoría; no debe
modificar `domain`, `topology`, `validation`, `powerfactory` ni `dgs`.

Para bases soportadas por SQLAlchemy basta normalmente una URL dialecto+driver y
la instalación del DBAPI correspondiente. Para nuevas extensiones vectoriales
soportadas por GDAL/OGR/GeoPandas puede forzarse `kind: vector` aunque la extensión
no figure en la detección automática.

## Contrato DGS

`DgsSchema` contiene:

- revisión del **formato DGS** cuando exista en `General/Version`;
- tablas/hojas;
- columnas tipadas;
- identidad/foreign key;
- parent pointers;
- referencias;
- transformaciones de unidades/convenciones;
- políticas de hojas no mapeadas.

No contiene `powerfactory_version` ni `digsilent_version`.
