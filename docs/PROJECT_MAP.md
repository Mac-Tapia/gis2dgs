# Mapa de responsabilidades

| Carpeta | Responsabilidad | No debe contener |
|---|---|---|
| `input/` | Lectura universal, DB, detección, merge, schema discovery, lectura por muestra | lógica PowerFactory/DGS |
| `assist/` | Propuesta de mapping YAML (NSGA-II, TOPSIS, LLM opcional) | escritura DGS, lógica de dominio |
| `gis/` | CRS, geometría, conectividad espacial | lógica de negocio general |
| `domain/` | Modelo eléctrico canónico | pandas, geopandas, SQL, DGS |
| `electrical/` | Tipos y parámetros eléctricos | readers de archivos |
| `topology/` | Grafo y tracing | acceso a archivos/DB |
| `validation/` | Reglas, readiness, reportes | lógica de lectura |
| `powerfactory/` | Modelo semántico node-breaker | formatos de entrada |
| `dgs/` | Schema/mapper/document/writer DGS | lógica del GIS de origen |
| `config/` | Configuración tipada | secretos |
| `cli/` | Comandos e interfaz de carga/ejecución | lógica eléctrica profunda |
| `tests/` | Evidencia automatizada | datos productivos secretos |
