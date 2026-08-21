# Fase 8 — Esquema, mapeo y serialización DGS

## Objetivo

Convertir el `PowerFactoryModel` semántico de la Fase 7 en un `DgsDocument` y
serializarlo usando un **esquema DGS estructural y neutral respecto de la versión de
DIgSILENT/PowerFactory**.

La Fase 8 no inventa nombres de columnas. `config/dgs_mapping.yaml` permanece
`configured: false` hasta inspeccionar un DGS de referencia real.

## Arquitectura

```text
NetworkModel + ElectricalLibrary
            ↓
PowerFactoryMapper                 Fase 7
            ↓
PowerFactoryModel
            ↓
DgsSchema                          Fase 8
            ↓
DgsMapper
            ↓
DgsDocument
 ├─ DgsTable
 └─ DgsRow
            ↓
DgsWriter
            ↓
DGS Excel
```

## Carpetas

```text
src/gis2dgs/dgs/
├── exceptions.py
├── mapper.py
├── models.py
├── schema.py           ← API canónica v0.8.1
├── profile.py          ← compatibilidad v0.8.0
├── template.py
├── validation.py
└── writer.py

src/gis2dgs/config/
└── dgs.py

config/
└── dgs_mapping.yaml
```

## Principios de diseño

1. La Fase 7 no conoce columnas DGS.
2. La Fase 8 es **schema-driven**: cada clase PowerFactory recibe un mapping explícito
   hacia tablas, columnas y referencias DGS.
3. No existe selector `powerfactory_version`, `digsilent_version` o `dgs_version`.
4. La compatibilidad se comprueba estructuralmente.
5. Un Excel DGS de referencia puede clonarse para preservar hojas/metadatos que el
   conversor no controla.
6. Los atributos y referencias semánticos no mapeados generan error en modo estricto.
7. La creación sin template está deshabilitada por defecto y solo se habilita
   explícitamente para desarrollo/pruebas.
8. Las foreign keys generadas se limitan a 40 caracteres y los IDs largos se acortan
   de forma determinista.

## `DgsSchema`

Es la API canónica de v0.8.1. Define:

- formato físico implementado;
- ruta opcional al DGS de referencia;
- filas de cabecera y datos;
- política de clases no mapeadas;
- modo estricto de atributos/referencias;
- mappings por clase PowerFactory.

`DgsMappingProfile` se conserva únicamente como alias de compatibilidad para código
v0.8.0.

## `DgsValueMapping`

Adapta un valor semántico a una columna DGS mediante:

- columna;
- `scale`;
- `offset`;
- `value_map` para booleanos/enums;
- `format_string`.

La transformación pertenece al esquema observado, no a un número de versión.

## `DgsReferenceMapping`

Convierte referencias semánticas de la Fase 7 hacia la columna declarada en el
esquema DGS.

## `DgsMapper`

Convierte:

```text
PowerFactoryObject
    foreign_key
    name
    parent
    attributes{}
    references{}
```

a:

```text
DgsRow
    object_key
    values{columna: valor}
```

## `DgsWriter`

- abre `.xlsx` o `.xlsm`;
- preserva hojas no gestionadas por defecto;
- verifica la existencia de hojas y columnas declaradas;
- limpia únicamente las columnas controladas antes de insertar datos;
- escribe las filas en la región configurada;
- guarda un archivo nuevo y no modifica el DGS de referencia.

## `inspect_excel_template`

Inspecciona un DGS Excel y devuelve:

- hojas;
- fila candidata de cabecera;
- columnas observadas;
- dimensiones.

```powershell
gis2dgs dgs inspect-template `
  data/reference/dgs_reference.xlsx `
  --output output/dgs/template_inspection.yaml
```

## Activación para un DGS real

1. Crear una red mínima representativa en PowerFactory.
2. Exportarla mediante DGS a Microsoft Excel.
3. Guardar una copia como `data/reference/dgs_reference.xlsx`.
4. Ejecutar el inspector.
5. Completar `config/dgs_mapping.yaml` con las tablas/columnas observadas.
6. Activar `configured: true`.
7. Ejecutar el pipeline y generar el DGS de salida.
8. Realizar la aceptación importándolo en PowerFactory.

## Checklist semántico del DGS de referencia

| Clase | Información a resolver |
|---|---|
| `ElmNet` | identidad/parent |
| `ElmSubstat` | coordenadas/parent |
| `ElmTerm` | tensión, coordenadas, feeder, parent |
| `StaCubic` | parent terminal, elemento conectado |
| `TypLne` | tensión, R/X/C, corriente, secuencia cero, fases |
| `ElmLne` | longitud, estado, tipo y cubículos terminales |
| `TypTr2` | Sn, HV/LV, uk, pérdidas, grupo vectorial, secuencia cero |
| `ElmTr2` | tensiones, Sn, estado, tipo, cubículos HV/LV |
| `ElmCoup` | estado, servicio, cubículos |
| `ElmLod` | P, Q, estado, cubículo |
| `ElmGenstat` | P, Q, tecnología/estado, cubículo |
| `ElmXnet` | tensión/estado, cubículo |

## Estado de cierre v0.8.1

- modelo `DgsSchema`: **IMPLEMENTADO**;
- mapping `PowerFactoryModel → DgsDocument`: **IMPLEMENTADO**;
- validación de `DgsDocument`: **IMPLEMENTADA**;
- writer Excel basado en esquema/template: **IMPLEMENTADO**;
- inspector de DGS Excel: **IMPLEMENTADO**;
- dependencia de versión PowerFactory/DIgSILENT: **ELIMINADA**;
- configuración concreta con datos del usuario: **PENDIENTE DE DGS REAL**;
- importación automática vía API: **FUERA DE ALCANCE; FASE 9**.
