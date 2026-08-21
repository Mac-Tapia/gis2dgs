# Estado de implementación — GIS2DGS 1.0.0

## Núcleo cerrado

| Área | Estado |
|---|---|
| Entorno VS Code / packaging / CLI | ✅ |
| Modelo eléctrico canónico | ✅ |
| Input universal por formatos y DB | ✅ |
| Schema discovery + merge | ✅ |
| Normalización + mapping configurable | ✅ |
| Topología / tracing / conectividad | ✅ |
| Validación integral | ✅ |
| Biblioteca eléctrica | ✅ |
| Modelo semántico PowerFactory node-breaker | ✅ |
| DGS schema / mapper / writer Excel | ✅ |
| Pruebas / auditoría / benchmark / wheel | ✅ |

## Extensiones futuras compatibles

No son defectos de 1.0.0 y pueden añadirse sin reescribir el núcleo:

- writers DGS ASCII/XML adicionales;
- GUI de escritorio/web;
- ejecución automática del import y estudios por PowerFactory API;
- procesamiento streaming/particionado para redes de millones de elementos;
- plugins de formatos físicos adicionales;
- modo incremental create/update/delete basado en snapshots/foreign keys.
