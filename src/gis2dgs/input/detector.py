from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from urllib.parse import urlparse

from .exceptions import UnsupportedInputError


class InputKind(StrEnum):
    AUTO = "auto"
    EXCEL = "excel"
    CSV = "csv"
    VECTOR = "vector"
    PARQUET = "parquet"
    DATABASE = "database"
    MSSQL_BACKUP = "mssql_backup"
    CYMDIST_TEXT = "cymdist_text"


_EXCEL = {".xlsx", ".xlsm", ".xls"}
_CSV = {".csv", ".tsv"}
_VECTOR = {".shp", ".gpkg", ".geojson", ".json", ".gml", ".kml"}
_PARQUET = {".parquet", ".pq"}
_DB_FILE = {".sqlite", ".sqlite3", ".db"}
_SQL_SCRIPT = {".sql"}
_DATABASE_SCHEMES = {
    "postgresql",
    "postgres",
    "mssql",
    "oracle",
    "sqlite",
    "mysql",
    "mariadb",
}

SQL_SCRIPT_ERROR = (
    "Un archivo .sql es un script, no una tabla ni una base de datos. "
    "GIS2DGS no lo lee. Exporte las tablas a Excel/CSV, use un SQLite "
    "(.db / .sqlite), o una URL en project.yaml "
    "(postgresql://, mssql://, sqlite:///archivo.db). "
    "Las consultas SELECT van en options.queries del YAML, no como archivo .sql."
)

SQL_SERVER_BACKUP_ERROR = (
    "Este archivo es una copia de seguridad de Microsoft SQL Server (.bak). "
    "GIS2DGS lo restaura en SQL Server y lee las tablas. "
    "Ejecute scripts/ensure_mssql.ps1 o configure GIS2DGS_MSSQL_URL hacia master. "
    "Cargue el .bak y pulse Ejecutar para inspeccionar; un project.yaml genera DGS."
)

_PROJECT_YAML = {".yaml", ".yml"}
_BACKUP = {".bak"}
_SQLITE_MAGIC = b"SQLite format 3"
_TAPE_MAGIC = b"TAPE"
_SQLSERVER_UTF16 = "Microsoft SQL".encode("utf-16le")


def programmed_file_suffixes() -> frozenset[str]:
    """File extensions the converter can detect, as programmed in this module."""
    return frozenset(_EXCEL | _CSV | _VECTOR | _PARQUET | _DB_FILE | _BACKUP | {".txt"})


def programmed_database_schemes() -> frozenset[str]:
    return frozenset(_DATABASE_SCHEMES)


def is_sqlite_file(path: Path) -> bool:
    header = _read_header(path)
    return header is not None and header.startswith(_SQLITE_MAGIC)


def is_geopackage_file(path: Path) -> bool:
    header = _read_header(path, size=80)
    return (
        header is not None
        and header.startswith(_SQLITE_MAGIC)
        and len(header) >= 72
        and header[68:72] == b"GPKG"
    )


def is_sql_server_backup(path: Path) -> bool:
    if path.suffix.lower() in _BACKUP:
        return True
    header = _read_header(path)
    if header is None or not header.startswith(_TAPE_MAGIC):
        return False
    return _SQLSERVER_UTF16 in header or b"Microsoft SQL" in header


def _read_header(path: Path, size: int = 256) -> bytes | None:
    if not path.is_file():
        return None
    try:
        with path.open("rb") as handle:
            return handle.read(size)
    except OSError:
        return None


def sniff_openable_kind(path: Path) -> InputKind | None:
    """Detect SQLite/GeoPackage from contents when the extension is missing."""
    if is_geopackage_file(path):
        return InputKind.VECTOR
    if is_sqlite_file(path):
        return InputKind.DATABASE
    return None


def iter_detectable_paths(root: Path, *, recursive: bool = False) -> tuple[Path, ...]:
    """List data files/folders under root using the programmed detector."""
    if not root.exists():
        return ()
    if root.is_dir() and root.suffix.lower() == ".gdb":
        return (root,)
    if not root.is_dir():
        return ()

    suffixes = programmed_file_suffixes()
    found: list[Path] = []
    iterator = root.rglob("*") if recursive else root.iterdir()
    for item in iterator:
        if "output" in item.parts:
            continue
        if item.is_dir() and item.suffix.lower() == ".gdb":
            found.append(item)
            continue
        if item.is_file() and item.suffix.lower() in suffixes:
            if item.suffix.lower() == ".txt":
                from .readers.cymdist_text import (
                    is_cymdist_import_config,
                    is_cymdist_network_export,
                )

                if not (
                    is_cymdist_network_export(item) or is_cymdist_import_config(item)
                ):
                    continue
            found.append(item)
            continue
        if item.is_file() and is_sql_server_backup(item):
            found.append(item)
            continue
        if item.is_file() and not item.suffix and sniff_openable_kind(item) is not None:
            found.append(item)
    return tuple(sorted(found, key=lambda path: str(path).lower()))


def detect_input_kind(uri: str | Path) -> InputKind:
    text = str(uri)
    parsed = urlparse(text)
    if parsed.scheme and parsed.scheme.split("+")[0].lower() in _DATABASE_SCHEMES:
        return InputKind.DATABASE

    path = Path(text)
    if path.is_dir() and path.suffix.lower() == ".gdb":
        return InputKind.VECTOR
    suffix = path.suffix.lower()
    if suffix in _SQL_SCRIPT:
        raise UnsupportedInputError(SQL_SCRIPT_ERROR)
    if suffix in _BACKUP:
        return InputKind.MSSQL_BACKUP
    if suffix in _EXCEL:
        return InputKind.EXCEL
    if suffix in _CSV:
        return InputKind.CSV
    if suffix in _VECTOR:
        return InputKind.VECTOR
    if suffix in _PARQUET:
        return InputKind.PARQUET
    if suffix == ".txt":
        from .readers.cymdist_text import (
            is_cymdist_import_config,
            is_cymdist_network_export,
        )

        if is_cymdist_network_export(path):
            return InputKind.CYMDIST_TEXT
        if is_cymdist_import_config(path):
            raise UnsupportedInputError(
                f"{path.name} es un archivo de configuración CYMDIST, no datos de red. "
                "Cargue la carpeta completa con RED/CARGA o seleccione esos archivos."
            )
    if suffix in _DB_FILE:
        return InputKind.DATABASE
    if path.is_file() and is_sql_server_backup(path):
        return InputKind.MSSQL_BACKUP
    sniffed = sniff_openable_kind(path) if path.is_file() else None
    if sniffed is not None:
        return sniffed
    raise UnsupportedInputError(f"Unable to detect input format for: {uri}")
