# Fase 6 — Biblioteca eléctrica canónica

## Objetivo

Resolver los `type_id` de líneas y transformadores contra una biblioteca eléctrica
independiente del GIS y del esquema DGS. Esta fase introduce parámetros físicos
necesarios para preparar estudios eléctricos sin acoplar el dominio a los nombres
de campos de PowerFactory.

## Componentes

### `src/gis2dgs/electrical/models.py`

- `LineType`: tensión nominal, R1/X1/C1, corriente admisible y datos opcionales R0/X0/C0.
- `TransformerType`: potencia, tensiones, uk, pérdidas, corriente en vacío, grupo vectorial
  y parámetros opcionales de secuencia cero.
- Cálculos derivados de impedancia para pruebas y consistencia física.

### `src/gis2dgs/electrical/library.py`

- `ElectricalLibrary`
- alta y consulta de tipos por identificador estable
- rechazo de duplicados
- error explícito para tipos desconocidos

### `src/gis2dgs/config/electrical_library.py`

Carga y valida `config/electrical_library.yaml` con Pydantic. El archivo de configuración
no contiene valores eléctricos inventados; debe completarse con datos aprobados por la
empresa, fabricantes o documentación técnica.

### `src/gis2dgs/validation/library_rules.py`

Comprueba:

- biblioteca obligatoria según perfil;
- `type_id` inexistente;
- tensión nominal línea ↔ tipo;
- tensiones HV/LV transformador ↔ tipo;
- potencia nominal transformador ↔ tipo;
- disponibilidad de parámetros de secuencia cero para el perfil `short_circuit`.

## Límites de la fase

Esta fase **no** transforma todavía los tipos a `TypLne` o `TypTr2`. Los nombres y
campos específicos de DGS se implementarán después de analizar un DGS patrón exportado
por el esquema DGS estructural configurado para el proyecto.
