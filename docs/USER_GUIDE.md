# Guía de uso — GIS2DGS 1.0.0

## Interfaz gráfica

Comandos para abrir la ventana y cargar el archivo:

```powershell
cd D:\converter\gisdgsv1
.\.venv\Scripts\Activate.ps1
.\RUN.ps1
```

o `python -m gis2dgs`.

1. **Cargar archivo…** → elija `examples\minimal\project.yaml` (para generar DGS).
2. **Ejecutar**.
3. **Abrir salida** → `minimal_dgs.xlsx`.

Un Excel suelto solo se inspecciona. La conversión exige un `project.yaml`.
Detalle clic a clic: `docs/GUIA_PASO_A_PASO.md`.

Un `project.yaml` convierte a DGS. Un archivo de datos solo inspecciona el esquema.
Secuencia del archivo real (cargar, verificar, convertir): `docs/GUIA_PASO_A_PASO.md`.
Los comandos equivalentes de PowerShell están en `docs/MANUAL_EJECUCION_CONSOLA.md`.

## Flujo recomendado

### A. Inventariar los datos de origen

```powershell
gis2dgs inspect-input datos.xlsx --output output/schema.yaml
gis2dgs suggest-mapping datos.xlsx --output output/suggested_mapping.yaml
```

Para una base de datos, configure una URL en variable de entorno y especifique
`kind: database` si la detección automática no aplica.

### B. Crear `mapping.yaml`

Asocie cada dataset lógico con su rol eléctrico. Ejemplo:

```yaml
buses:
  source: NODOS
  fields:
    id: COD_NODO
    name: NOMBRE
    nominal_voltage_kv: TENSION_KV
    x: ESTE
    y: NORTE

lines:
  source: TRAMOS
  fields:
    id: COD_TRAMO
    from_bus: NODO_I
    to_bus: NODO_F
    length_km: LONG_KM
    nominal_voltage_kv: TENSION_KV
    type_id: COD_COND
```

### C. Cargar biblioteca eléctrica

`electrical_library.yaml` almacena tipos de línea y transformador. No se deben
inventar impedancias: use datos de fabricante, empresa o fuente técnica validada.

### D. Seleccionar política de validación

- `standard`: consistencia general.
- `geographic`: además exige coordenadas.
- `radial_distribution`: exige radialidad según política.
- `power_flow`: exige fuente y tipos necesarios.
- `short_circuit`: exige además datos de secuencia cero.

### E. Configurar PowerFactory y DGS

Use un DGS real exportado como plantilla de estructura:

```powershell
gis2dgs dgs inspect-template SALIDA_DGS.xlsx --output output/dgs_schema.yaml
```

Configure las columnas reales en `dgs_mapping.yaml`. El campo
`dgs_format_version`, si se usa, corresponde a `General/Version` del formato DGS,
no a una versión del producto PowerFactory.

### F. Convertir

```powershell
gis2dgs convert project.yaml --json
```

### G. Importar en PowerFactory

Abra PowerFactory y utilice la función estándar de importación DGS con el Excel
generado. Valide el log de importación y ejecute primero un flujo de carga antes
de utilizar el modelo para otros estudios.

## Diagnóstico

El pipeline produce:

- schema report de entrada;
- reporte JSON de validación;
- reporte CSV de validación;
- DGS Excel.

No ignore errores `STRUCTURE`, `ELECTRICAL`, `READINESS` o referencias faltantes.
