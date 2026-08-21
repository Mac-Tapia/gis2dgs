# Requires GIS2DGS_MSSQL_URL (or a reachable local/Docker instance).
# Creates a tiny network database, backs it up under output/, restores it
# with MssqlBackupReader and optionally converts to DGS.
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis2dgs.config import load_project_config  # noqa: E402
from gis2dgs.input.dataset import InputDataset  # noqa: E402
from gis2dgs.input.readers.mssql_backup import (  # noqa: E402
    MISSING_SERVER_ERROR,
    MssqlBackupReader,
    database_url,
    execute_odbc_ddl,
    probe_sql_server,
    sanitize_database_name,
    sql_ident,
    sql_literal,
)
from gis2dgs.pipeline import run_conversion  # noqa: E402

FIXTURE_DB = "gis2dgs_fixture"
RESTORE_DB = "gis2dgs_restore"
BACKUP_NAME = "gis2dgs_fixture.bak"
TABLES = ("buses", "lines", "loads", "sources")


def _engine(url: str):
    return create_engine(url, isolation_level="AUTOCOMMIT")


def _server_backup_disk() -> tuple[str, Path]:
    server_dir = os.environ.get("GIS2DGS_MSSQL_SERVER_BACKUP_DIR", "").strip()
    host_dir = Path(
        os.environ.get("GIS2DGS_MSSQL_HOST_STAGE_DIR", str(ROOT / "output" / "mssql" / "backup"))
    )
    host_dir.mkdir(parents=True, exist_ok=True)
    host_file = host_dir / BACKUP_NAME
    if server_dir:
        server_root = server_dir.replace("\\", "/").rstrip("/")
        disk = f"{server_root}/{BACKUP_NAME}"
    else:
        disk = str(host_file.resolve())
    return disk, host_file


def _load_minimal_frames() -> dict[str, pd.DataFrame]:
    folder = ROOT / "examples" / "minimal" / "input"
    return {
        name: pd.read_csv(folder / f"{name}.csv")
        for name in TABLES
    }


def create_fixture_database(url: str) -> None:
    engine = _engine(url)
    frames = _load_minimal_frames()
    ident = sql_ident(FIXTURE_DB)
    try:
        with engine.connect() as connection:
            execute_odbc_ddl(
                connection,
                f"IF DB_ID({sql_literal(FIXTURE_DB)}) IS NOT NULL "
                f"ALTER DATABASE {ident} SET SINGLE_USER WITH ROLLBACK IMMEDIATE",
            )
            execute_odbc_ddl(
                connection,
                f"IF DB_ID({sql_literal(FIXTURE_DB)}) IS NOT NULL "
                f"DROP DATABASE {ident}",
            )
            execute_odbc_ddl(connection, f"CREATE DATABASE {ident}")
        fixture_url = database_url(url, FIXTURE_DB)
        data_engine = create_engine(fixture_url)
        try:
            for name, frame in frames.items():
                frame.to_sql(name, data_engine, index=False, if_exists="replace")
        finally:
            data_engine.dispose()
        disk, _host = _server_backup_disk()
        with engine.connect() as connection:
            execute_odbc_ddl(
                connection,
                f"ALTER DATABASE {ident} SET SINGLE_USER WITH ROLLBACK IMMEDIATE",
            )
            execute_odbc_ddl(
                connection,
                f"BACKUP DATABASE {ident} TO DISK = {sql_literal(disk)} "
                "WITH INIT, COPY_ONLY",
            )
            execute_odbc_ddl(connection, f"ALTER DATABASE {ident} SET MULTI_USER")
    finally:
        engine.dispose()


def restore_and_read(url: str, backup: Path) -> InputDataset:
    reader = MssqlBackupReader(
        backup,
        source_id="network_db",
        server_url=url,
        restore_database=RESTORE_DB,
        replace=True,
    )
    return reader.read()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a tiny .bak, restore it and optionally convert to DGS."
    )
    parser.add_argument(
        "--convert",
        action="store_true",
        help="Run examples/mssql_backup/project.yaml after restore.",
    )
    args = parser.parse_args()
    url = probe_sql_server(os.environ.get("GIS2DGS_MSSQL_URL"))
    if not url:
        print(MISSING_SERVER_ERROR, file=sys.stderr)
        return 2
    disk, host_file = _server_backup_disk()
    create_fixture_database(url)
    if not host_file.exists():
        print(f"El backup no apareció en el host: {host_file}", file=sys.stderr)
        print(f"Ruta vista por SQL Server: {disk}", file=sys.stderr)
        return 3
    os.environ["GIS2DGS_MSSQL_BACKUP"] = str(host_file.resolve())
    os.environ["GIS2DGS_MSSQL_URL"] = url
    dataset = restore_and_read(url, host_file)
    names = sorted(dataset.tables)
    expected = set(TABLES)
    report = {
        "ok": expected.issubset(set(names)),
        "backup": str(host_file),
        "tables": names,
        "restore_database": sanitize_database_name(RESTORE_DB),
        "server_url_configured": True,
    }
    if args.convert:
        project = load_project_config(ROOT / "examples" / "mssql_backup" / "project.yaml")
        result = run_conversion(project)
        report["convert"] = result.as_dict()
        report["ok"] = bool(report["ok"] and result.buses == 2 and result.lines == 1)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
