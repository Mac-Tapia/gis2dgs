from pathlib import Path

import pytest

from gis2dgs.input import (
    InputKind,
    UnsupportedInputError,
    detect_input_kind,
    iter_detectable_paths,
    programmed_database_schemes,
    programmed_file_suffixes,
)


@pytest.mark.parametrize(
    ("value", "kind"),
    [
        ("network.xlsx", InputKind.EXCEL),
        ("network.csv", InputKind.CSV),
        ("network.shp", InputKind.VECTOR),
        ("network.gpkg", InputKind.VECTOR),
        ("network.geojson", InputKind.VECTOR),
        ("network.parquet", InputKind.PARQUET),
        ("network.pq", InputKind.PARQUET),
        ("network.kml", InputKind.VECTOR),
        ("network.gml", InputKind.VECTOR),
        ("network.sqlite", InputKind.DATABASE),
        ("network.sqlite3", InputKind.DATABASE),
        ("network.db", InputKind.DATABASE),
        ("mysql://u:p@host/db", InputKind.DATABASE),
        ("oracle://u:p@host/db", InputKind.DATABASE),
        ("postgresql+psycopg://u:p@host/db", InputKind.DATABASE),
        ("mssql+pyodbc://u:p@dsn/db", InputKind.DATABASE),
    ],
)
def test_detect_input_kind(value: str, kind: InputKind) -> None:
    assert detect_input_kind(value) == kind


def test_unknown_extension_is_rejected() -> None:
    with pytest.raises(UnsupportedInputError):
        detect_input_kind(Path("network.unknown"))


def test_sql_script_is_rejected_with_guidance() -> None:
    with pytest.raises(UnsupportedInputError, match="script"):
        detect_input_kind(Path("red.sql"))


def test_sql_server_backup_extension_is_detected() -> None:
    assert detect_input_kind(Path("ELOR25_V1.bak")) == InputKind.MSSQL_BACKUP


def test_sql_server_backup_without_extension_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "ELOR25_V1"
    payload = b"TAPE" + b"\x00" * 40 + "Microsoft SQL".encode("utf-16le") + b"\x00" * 20
    path.write_bytes(payload)
    assert detect_input_kind(path) == InputKind.MSSQL_BACKUP


def test_sqlite_without_extension_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "red"
    path.write_bytes(b"SQLite format 3\x00" + b"\x00" * 80)
    assert detect_input_kind(path) == InputKind.DATABASE


def test_programmed_suffixes_cover_supported_inputs() -> None:
    suffixes = programmed_file_suffixes()
    for suffix in (
        ".xlsx",
        ".xlsm",
        ".xls",
        ".csv",
        ".tsv",
        ".shp",
        ".gpkg",
        ".geojson",
        ".json",
        ".gml",
        ".kml",
        ".parquet",
        ".pq",
        ".sqlite",
        ".sqlite3",
        ".db",
        ".bak",
    ):
        assert suffix in suffixes
    assert ".sql" not in suffixes
    assert "postgresql" in programmed_database_schemes()
    assert "mssql" in programmed_database_schemes()


def test_iter_detectable_paths_finds_programmed_files(tmp_path: Path) -> None:
    (tmp_path / "buses.csv").write_text("id\nB1\n", encoding="utf-8")
    (tmp_path / "red.xlsx").write_bytes(b"")
    (tmp_path / "notes.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "readme.txt").write_text("x", encoding="utf-8")
    found = {path.name for path in iter_detectable_paths(tmp_path)}
    assert found == {"buses.csv", "red.xlsx"}
