# Certificación y benchmark — GIS2DGS 1.0.0

## Veredicto experto: no usar DL/transformers en el runtime

**No.** El conversor no debe entrenar ni cargar modelos de deep learning ni transformers
(HuggingFace/PyTorch) para integrar tablas en un DGS listo para DIgSILENT PowerFactory.

Razones de ingeniería:

1. **La precisión del DGS no es un problema de embeddings.** Un import correcto exige IDs
   deterministas, claves foráneas, unidades, topología y validación eléctrica. Un modelo
   generativo puede alucinar un bus, una impedancia o un tipo; eso rompe PowerFactory o,
   peor, importa una red equivocada.
2. **No hay entrenamiento en este proyecto.** Sin un corpus etiquetado por esquema de
   empresa, un transformer genérico es peor que el matching léxico ya programado.
3. **El conversor debe ejecutarse offline**, sin GPU ni pesos. Torch/transformers
   convertirían GIS2DGS en un pipeline de investigación y romperían `convert` en
   estaciones de trabajo normales.
4. **El flujo canónico no se salta.** `InputDataset → mapping YAML → NetworkModel →
   validación → PowerFactoryModel → DGS`. Meter un modelo en esa cadena incentiva
   escribir DGS desde una tabla.
5. **Ya existe el sitio correcto para “mapping más inteligente”:** `suggest-mapping`
   (NSGA-II + TOPSIS). Un LLM HTTP opcional (`GIS2DGS_LLM_URL`, stdlib, fail-open)
   puede refinar el YAML; **nunca escribe DGS**. `convert` no lo requiere.

Los transformers eléctricos (`ElmTr2`, capas `transformers` del mapping) no tienen
relación con transformers de NLP.

## Qué mide el benchmark

Script reproducible:

```powershell
python scripts\benchmark_converter.py
```

Escribe `output/certification_benchmark.json` (no toca `data/reference/real/`). Comprueba:

| Check | Criterio de PASS |
|---|---|
| Ejemplo `examples/minimal` | 2 buses, 1 línea, 1 carga, 1 fuente; existe el DGS |
| Precisión de mapping | 100 % en esquema español (`nodos`/`tramos`/…) y en CSV mínimos |
| Inspect vs convert | Tiempos y pico `tracemalloc` (asignaciones Python, no RSS nativo) |
| Offline | `convert` sin `GIS2DGS_LLM_URL` y sin importar `torch`/`transformers` |
| `.bak` / mssql | Detector y reader sin motor en vivo; restore implementado (`ensure_mssql.ps1`) |
| Independencia | `domain/` sin pandas/DB; `pipeline` usa NetworkModel + validación |

## Cómo convertir y proponer mapping

```powershell
python -m gis2dgs inspect-input examples\minimal\input --output output\input_schema.yaml
python -m gis2dgs suggest-mapping examples\minimal\input --output output\suggested_mapping.yaml
python -m gis2dgs convert examples\minimal\project.yaml --json
```

`--llm` es opcional y exige `GIS2DGS_LLM_URL` + `GIS2DGS_LLM_API_KEY`. Si faltan, el
asistente sigue con NSGA-II + TOPSIS.

Un `.bak` se restaura con el motor SQL Server (`scripts/ensure_mssql.ps1` o
`GIS2DGS_MSSQL_URL`). La certificación cubre detección y reader **sin** exigir
ese proceso en cada `pytest`; la prueba `mssql` lo ejercita cuando el motor existe.

La aceptación final en DIgSILENT (File > Import > DGS + flujo de carga) no la sustituye
este benchmark.
