# Evaluación de rendimiento — GIS2DGS 1.0.0

## Benchmark de topología

Comando:

```powershell
python scripts/benchmark_topology.py --nodes 50000
```

Entorno de auditoría: Linux x86_64, Python 3.13.5.

Resultado de una ejecución medida:

```text
nodes=50000
lines=49999
topology elapsed_seconds=2.327961
islands=1
energized=50000
wall clock total=3.23 s
maximum resident set size=259264 KB (~253 MiB)
```

La auditoría integrada registró una segunda medición de ~2.54 s para el análisis
topológico de la misma red. La variación es esperable por carga del entorno.

## Interpretación

El benchmark demuestra viabilidad práctica para redes de decenas de miles de
barras en el entorno probado. No constituye un SLA para cualquier hardware o
esquema de datos.

## Decisiones de escalabilidad

- `networkx.MultiGraph` preserva circuitos paralelos.
- El merge de múltiples fuentes es lineal respecto al número de tablas y evita
  recopiado acumulativo del dataset completo.
- Bases SQL pueden filtrarse por tablas/vistas/queries antes de entrar al pipeline.
- El pipeline principal es in-memory. Para millones de elementos se recomienda
  particionar por área/alimentador o desarrollar un backend streaming/particionado
  conservando las interfaces actuales.
