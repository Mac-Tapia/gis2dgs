# Guía — cargar el archivo en la interfaz y convertirlo a DGS

La conversión desde la ventana es: **abrir interfaz → Cargar archivo/carpeta → Ejecutar**.

`RUN`/`load` aplica un flujo único integral por tipo detectado: inspección → mapping
→ `NetworkModel` → validación → DGS (excepto una plantilla DGS de referencia, que se
inspecciona como esquema).

## Dónde queda lo que carga y lo que genera

La interfaz **no copia ni guarda** el archivo que usted elige. Lo lee en el sitio
donde está (su Escritorio, Descargas, USB, etc.).

| Qué | Dónde |
| --- | --- |
| Archivo que cargó (Excel, CSV, YAML, …) | Sigue en **su carpeta original**. No se mueve. |
| Esquema y artefactos al pulsar Ejecutar sobre datos (Excel/CSV/SHP/.bak/DB) | `output\loaded\<nombre>\output\input_schema.yaml` + `project.yaml` + `red_dgs.xlsx` |
| DGS al pulsar Ejecutar sobre `project.yaml` | La ruta `output_dgs` de ese YAML, p. ej. `examples\minimal\output\minimal_dgs.xlsx` |
| Validación | `validation.json` / `validation.csv` junto al DGS |

Pulse **Abrir salida** para ir a la carpeta de resultados (`output\` del proyecto).

## Backup SQL Server → DGS

El restore de `.bak` **está implementado**: GIS2DGS ejecuta `RESTORE FILELISTONLY` +
`RESTORE DATABASE` y lee las tablas. Lo único externo es un **proceso SQL Server**
(instalado, LocalDB/Express o Docker). Eso no es código pendiente: el formato Microsoft
no se desempaqueta como carpeta de tablas sin el motor.

### 1. Comprobar o arrancar SQL Server

```powershell
. .\scripts\ensure_mssql.ps1
```

El script, en este orden: usa `GIS2DGS_MSSQL_URL` si ya conecta; prueba `localhost` /
Express / LocalDB con autenticación Windows; si no hay motor y Docker está en marcha,
arranca `mcr.microsoft.com/mssql/server:2022-CU16-ubuntu-22.04` (`docker-compose.mssql.yml`)
con la contraseña SA en `GIS2DGS_MSSQL_SA_PASSWORD` (nunca se versiona; puede generarse en
`output\mssql\.sa_password`). Hace `docker pull` con reintentos y reutiliza la imagen local
si ya está descargada. Deja las variables en la sesión y en
`output\mssql\session.env.ps1`.

Si MCR no responde (TLS timeout), ejecute
`docker pull mcr.microsoft.com/mssql/server:2022-CU16-ubuntu-22.04` o defina
`GIS2DGS_MSSQL_URL` hacia un SQL Server local.

Instancia ya existente, sin Docker:

```powershell
$env:GIS2DGS_MSSQL_URL = "mssql+pyodbc://usuario:clave@servidor\instancia/master?driver=ODBC+Driver+17+for+SQL+Server"
```

En el mismo PC suele bastar Trusted_Connection (`localhost`). El servicio debe poder
leer el `.bak` (o, con Docker, el archivo se copia a `output\mssql\backup`).
Un backup sin extensión con cabecera `TAPE` (por ejemplo `ELOR25_V1`) se detecta
igual que un `.bak`.

Hace falta el Microsoft ODBC Driver 17 u 18. Detalle: `docs\SYSTEM_REQUIREMENTS.md`.

Reproducción con un `.bak` sintético pequeño (solo si el motor ya responde):

```powershell
python scripts\mssql_backup_roundtrip.py --convert
```

### 2. Cargar el backup en la interfaz (inspeccionar tablas)

1. `. .\scripts\ensure_mssql.ps1` y luego `.\RUN.ps1`
2. **Cargar archivo…** → su `.bak` (o un backup sin extensión con cabecera `TAPE`)
3. Tipo: **Backup SQL Server**
4. **Ejecutar** → inspect → mapping → `NetworkModel` → validación → DGS

Equivalente (flujo completo en un comando):

```powershell
python -m gis2dgs load C:\ruta\red.bak --json
```

### 3. Convertir a DGS

`examples\mssql_backup` ya trae mapping, biblioteca eléctrica, validación y esquema DGS
(plantilla de tablas `buses` / `lines` / `loads` / `sources`). Un comando:

```powershell
$env:GIS2DGS_MSSQL_BACKUP = "C:\ruta\red.bak"
python -m gis2dgs convert examples\mssql_backup\project.yaml --json
```

O en la interfaz: **Cargar archivo…** → `examples\mssql_backup\project.yaml` → **Ejecutar**.

El DGS queda en `examples\mssql_backup\output\red_dgs.xlsx` cuando la validación pasa.
No se escribe DGS desde una tabla: el flujo sigue `NetworkModel` y validación.

## Proponer mapping (NSGA-II + TOPSIS)

Si las columnas no coinciden con el YAML de ejemplo, **no se salta el pipeline**: se propone
un `mapping.yaml` y luego `convert` sigue `NetworkModel → validación → DGS`.

En la interfaz, con el backup o una carpeta de tablas cargada:

1. **Proponer mapping**
2. Revise `output\suggested_mapping.yaml` y el informe Pareto `output\suggested_mapping_report.yaml`
3. Copie el mapping al `project.yaml` (o apunte `mapping:` a ese archivo)
4. **Cargar archivo…** el `project.yaml` → **Ejecutar**

Equivalente:

```powershell
python -m gis2dgs suggest-mapping $env:GIS2DGS_MSSQL_BACKUP --output output\suggested_mapping.yaml
python -m gis2dgs suggest-mapping examples\minimal\input --output output\suggested_mapping.yaml
Copy-Item output\suggested_mapping.yaml examples\mssql_backup\config\mapping.yaml
```

Archivos grandes: por defecto se perfilan hasta 100000 filas por tabla
(`--sample-rows 0` lee todo; o `$env:GIS2DGS_SAMPLE_ROWS = "0"`).
LLM opcional: `GIS2DGS_LLM_URL` + `GIS2DGS_LLM_API_KEY` y `--llm`.
No instala PyTorch ni modelos locales: el conversor sigue siendo el núcleo.

## Archivo .sql: no se reconoce (es correcto)

Un `.sql` es un **script** (`CREATE TABLE`, `INSERT`, `SELECT…`), no una tabla de datos.
GIS2DGS no lo abre.

Use una de estas entradas:

1. Exporte las tablas a **Excel o CSV** y cárguelas en la interfaz.
2. Cargue un SQLite **`.db` / `.sqlite`** (base ya creada, no el script).
3. En `project.yaml`, una **URL de base** (no un `.sql`):

```yaml
inputs:
  sources:
    - id: red_db
      uri: $GIS2DGS_DB_URL
      kind: database
      options:
        tables: [nodos, tramos]
```

```powershell
$env:GIS2DGS_DB_URL = "postgresql+psycopg://usuario:clave@servidor:5432/red"
```

Consultas SQL van en `options.queries` del YAML, no como archivo `.sql` suelto.

## Qué detecta la interfaz (como está programado el conversor)

Al cargar **`project.yaml`** o **Cargar carpeta…** sobre `examples\minimal`, lista **todas** las fuentes del proyecto y su formato:

- Excel: `.xlsx` `.xlsm` `.xls`
- Tablas: `.csv` `.tsv`
- Vector: `.shp` `.gpkg` `.geojson` `.json` `.gml` `.kml` y carpeta `.gdb`
- Parquet: `.parquet` `.pq`
- SQLite: `.sqlite` `.sqlite3` `.db`
- Bases por URL: `postgresql://` `mssql://` `oracle://` `mysql://` `sqlite://`

**Cargar carpeta…** sobre `examples\minimal\input` detecta los cuatro CSV (`buses`, `lines`, `loads`, `sources`).

**Cargar carpeta…** sobre `examples\minimal` detecta el `project.yaml` y, al Ejecutar, convierte las cuatro tablas.

---

## 1. Comando para abrir la interfaz

En PowerShell, en la carpeta del proyecto:

```powershell
cd D:\converter\gisdgsv1
.\.venv\Scripts\Activate.ps1
.\RUN.ps1
```

Equivale a cualquiera de estos:

```powershell
python -m gis2dgs
```

```powershell
python -m gis2dgs gui
```

Si no existe `.venv`:

```powershell
.\INSTALL_AND_VERIFY.ps1
```

y después otra vez `.\RUN.ps1`.

Se abre la ventana **GIS2DGS** y, enseguida, el diálogo **Seleccione el archivo a cargar**.

---

## 2. Cargar el archivo en la interfaz (conversión a DGS)

En la ventana hay tres botones:

`Cargar archivo…`    `Ejecutar`    `Abrir salida`

### Conversión que ya funciona (hágalo primero)

1. Pulse **Cargar archivo…** (si el diálogo no salió solo).
2. Vaya a la carpeta del proyecto.
3. Abra `examples` → `minimal`.
4. Seleccione **`project.yaml`** (no el CSV, no el Excel).
5. Pulse **Abrir**.
6. Compruebe en la ventana:
   - `Archivo: ...\examples\minimal\project.yaml`
   - `Tipo: Proyecto: minimal-end-to-end`
7. Pulse **Ejecutar**.
8. Espere `Ejecución correcta.`
9. Pulse **Abrir salida**.

DGS generado:

`examples\minimal\output\minimal_dgs.xlsx`

Validación:

`examples\minimal\output\validation.json` → debe tener `"valid": true`

Eso es **cargar desde la interfaz y convertir**.

### Si cargó un Excel/CSV/SHP/.bak/DB

La ventana dirá `Tipo: Datos de entrada` o `Backup SQL Server`. **Ejecutar** corre
el flujo completo y deja resultados en `output\loaded\<nombre>\`.
Si faltan referencias críticas (por ejemplo buses inexistentes o conexión a DB),
la ejecución falla con mensaje claro y sin inventar datos/objetos.

---

## 3. Cargar un archivo real en la interfaz (verificar, luego convertir)

### 3.1 Copiar el archivo real (no tocar `data\reference\real\`)

```powershell
cd D:\converter\gisdgsv1
New-Item -ItemType Directory -Force output\entrada | Out-Null
Copy-Item data\reference\real\M_ALIMENTAD.xlsx output\entrada\M_ALIMENTAD.xlsx
```

Su archivo nuevo:

```powershell
Copy-Item "C:\ruta\SU_ARCHIVO.xlsx" output\entrada\red.xlsx
```

### 3.2 Verificarlo en la interfaz

1. `.\RUN.ps1`
2. **Cargar archivo…**
3. Elija `output\entrada\M_ALIMENTAD.xlsx` (o `red.xlsx`).
4. **Ejecutar**.

Eso dispara el flujo integral y deja artefactos en `output\loaded\...`.
Si quiere solo verificar esquema, use:

```powershell
python -m gis2dgs inspect-input output\entrada\M_ALIMENTAD.xlsx --output output\input_schema.yaml
```

Con `load`/GUI sí hay DGS cuando los datos son consistentes y pasan validación.

### 3.3 Convertir el archivo real desde la interfaz

La interfaz también convierte cuando carga datos sueltos soportados, porque crea
un proyecto temporal y ejecuta el pipeline integral.

1. Prepare `output\mi_proyecto\project.yaml` apuntando a `output\entrada\...` (paso 5 más abajo).
2. `.\RUN.ps1`
3. **Cargar archivo…**
4. Elija `output\mi_proyecto\project.yaml`
5. **Ejecutar**
6. **Abrir salida** → el DGS está ahí.

Equivale al comando:

```powershell
python -m gis2dgs convert output\mi_proyecto\project.yaml --json
```

---

## 4. Qué archivo elegir en **Cargar archivo…**

| Quiere | En el diálogo elija | Al pulsar Ejecutar |
| --- | --- | --- |
| **Convertir a DGS** | `project.yaml` | Genera el Excel DGS |
| Solo ver columnas del Excel/CSV/SHP | el archivo de datos | Inspección, sin DGS |
| Ver estructura de un DGS de referencia | `SALIDA_DGS.xlsx` | Inspección DGS |

Rutas listas para el diálogo:

- Convertir ahora: `D:\converter\gisdgsv1\examples\minimal\project.yaml`
- Verificar real: `D:\converter\gisdgsv1\output\entrada\M_ALIMENTAD.xlsx`
- Convertir real (cuando exista el proyecto): `D:\converter\gisdgsv1\output\mi_proyecto\project.yaml`

---

## 5. Preparar `project.yaml` para un archivo real (antes de cargarlo en la interfaz)

```powershell
Copy-Item -Recurse examples\minimal output\mi_proyecto
```

En `output\mi_proyecto\project.yaml` ponga su archivo en `inputs.sources[].uri`, por ejemplo `../entrada/red.xlsx`.
En `config\mapping.yaml` use los nombres de columna que salieron al verificar el Excel.

`M_ALIMENTAD.xlsx` es una tabla de alimentadores. La conversión a red DGS necesita barras, líneas y una fuente mapeadas. Si su exportación trae varios archivos, declare cada uno en `project.yaml` y después cárguelo en la interfaz.

---

## 6. Misma conversión por consola (si no usa la ventana)

Abrir interfaz:

```powershell
.\RUN.ps1
python -m gis2dgs
python -m gis2dgs gui
```

Cargar y verificar un Excel:

```powershell
python -m gis2dgs inspect-input output\entrada\M_ALIMENTAD.xlsx --output output\input_schema.yaml
```

Convertir (el archivo que la interfaz carga para DGS):

```powershell
python -m gis2dgs convert examples\minimal\project.yaml --json
python -m gis2dgs convert output\mi_proyecto\project.yaml --json
```

Plantilla DGS real:

```powershell
python -m gis2dgs dgs inspect-template data\reference\real\SALIDA_DGS.xlsx --output output\dgs_schema.yaml
```

---

## 7. Después de Ejecutar: PowerFactory

1. Pulse **Abrir salida** o vaya a la carpeta `output` del proyecto.
2. En PowerFactory: `File > Import > DGS`.
3. Elija el `.xlsx` generado (no el de `data\reference\real\`).
4. Revise el log y ejecute un flujo de carga.

`validation.json` debe mostrar `"valid": true` y `"errors": 0`.
