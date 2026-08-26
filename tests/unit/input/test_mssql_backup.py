from pathlib import Path
from unittest.mock import MagicMock

import yaml

from gis2dgs.input import InputKind, InputReaderFactory
from gis2dgs.input.readers.mssql_backup import (
    MISSING_SERVER_ERROR,
    MssqlBackupReader,
    _drop_db_if_exists,
    _moves_from_filelist,
    database_url,
    docker_master_url,
    filelist_sql,
    is_server_posix_path,
    odbc_master_url,
    resolve_restore_disk,
    restore_sql,
    sanitize_database_name,
    single_user_sql,
)


def test_sanitize_database_name() -> None:
    assert sanitize_database_name("ELOR25_V1") == "ELOR25_V1"
    assert sanitize_database_name("25red") == "db_25red"


def test_restore_sql_moves_files(tmp_path: Path) -> None:
    backup = tmp_path / "ELOR25_V1.bak"
    data = tmp_path / "ELOR.mdf"
    log = tmp_path / "ELOR.ldf"
    sql = restore_sql(backup, "ELOR25_V1", [("elor_data", data), ("elor_log", log)])
    assert "RESTORE DATABASE [ELOR25_V1]" in sql
    assert "REPLACE" in sql
    assert "elor_data" in sql
    assert str(data.resolve()) in sql


def test_filelist_sql_quotes_path(tmp_path: Path) -> None:
    backup = tmp_path / "a'b.bak"
    sql = filelist_sql(backup)
    assert "RESTORE FILELISTONLY" in sql
    assert "''" in sql


def test_database_url_replaces_database() -> None:
    url = database_url(
        "mssql+pyodbc://u:p@localhost/master?driver=ODBC+Driver+17+for+SQL+Server",
        "ELOR25_V1",
    )
    assert "ELOR25_V1" in url
    assert "master" not in url.split("?")[0]


def test_factory_creates_mssql_backup_reader(tmp_path: Path) -> None:
    path = tmp_path / "red.bak"
    path.write_bytes(b"TAPE")
    reader = InputReaderFactory.create(path, kind=InputKind.AUTO)
    assert isinstance(reader, MssqlBackupReader)


def test_probe_invalid_explicit_url_returns_none(monkeypatch) -> None:
    from gis2dgs.input.readers.mssql_backup import ProbeStatus, probe_sql_server

    monkeypatch.delenv("GIS2DGS_MSSQL_SA_PASSWORD", raising=False)
    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.connection_candidates",
        lambda explicit_url=None: (explicit_url,) if explicit_url else (),
    )
    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.probe_sql_auth_variants",
        lambda **kwargs: ProbeStatus(None),
    )
    assert probe_sql_server(
        "mssql+pyodbc://127.0.0.1:1/master?driver=ODBC+Driver+17+for+SQL+Server"
    ) is None


def test_missing_server_error_points_to_ensure_script() -> None:
    assert "ensure_mssql.ps1" in MISSING_SERVER_ERROR
    assert "implementado" in MISSING_SERVER_ERROR.lower()


def test_docker_url_encodes_password(monkeypatch) -> None:
    from urllib.parse import unquote_plus

    monkeypatch.setenv("GIS2DGS_MSSQL_SA_PASSWORD", "Gis2dgs_Dev1!")
    monkeypatch.setenv("GIS2DGS_MSSQL_HOST", "127.0.0.1")
    monkeypatch.setenv("GIS2DGS_MSSQL_PORT", "1433")
    url = docker_master_url(driver="ODBC Driver 18 for SQL Server")
    assert url is not None
    assert "odbc_connect=" in url
    raw = unquote_plus(url.split("odbc_connect=", 1)[1])
    assert "Gis2dgs_Dev1!" in raw
    assert "127.0.0.1,1433" in raw
    assert "UID=sa" in raw
    assert "Authentication=SqlPassword" in raw
    assert "Trusted_Connection" not in raw


def test_docker_url_absent_without_password(monkeypatch) -> None:
    monkeypatch.delenv("GIS2DGS_MSSQL_SA_PASSWORD", raising=False)
    assert docker_master_url() is None


def test_odbc_trusted_url_uses_driver() -> None:
    url = odbc_master_url(
        "localhost",
        trusted=True,
        driver="ODBC Driver 17 for SQL Server",
    )
    assert "Trusted_Connection=yes" in url
    assert "ODBC+Driver+17+for+SQL+Server" in url
    assert "TrustServerCertificate=yes" in url
    assert "Authentication=SqlPassword" not in url


def test_has_modern_odbc_driver() -> None:
    from gis2dgs.input.readers.mssql_backup import has_modern_odbc_driver

    assert has_modern_odbc_driver(("ODBC Driver 18 for SQL Server",))
    assert has_modern_odbc_driver(("ODBC Driver 17 for SQL Server",))
    assert not has_modern_odbc_driver(("SQL Server",))
    assert not has_modern_odbc_driver(())


def test_installed_odbc_drivers_do_not_invent_modern_names(monkeypatch) -> None:
    import sys

    from gis2dgs.input.readers.mssql_backup import installed_odbc_drivers

    class FakePyodbc:
        @staticmethod
        def drivers():
            return ["SQL Server"]

    monkeypatch.setitem(sys.modules, "pyodbc", FakePyodbc)
    names = installed_odbc_drivers()
    assert names == ("SQL Server",)
    assert not any("ODBC Driver" in name for name in names)


def test_docker_candidates_skip_windows_auth(monkeypatch) -> None:
    from gis2dgs.input.readers.mssql_backup import (
        connection_candidates,
        decode_odbc_connect,
    )

    monkeypatch.setenv("GIS2DGS_MSSQL_DOCKER", "true")
    monkeypatch.setenv("GIS2DGS_MSSQL_SA_PASSWORD", "Gis2dgs_Dev1!")
    monkeypatch.setenv("GIS2DGS_MSSQL_HOST", "127.0.0.1")
    monkeypatch.setenv("GIS2DGS_MSSQL_PORT", "1433")
    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.installed_odbc_drivers",
        lambda: ("ODBC Driver 18 for SQL Server",),
    )
    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup._tcp_open",
        lambda host, port, timeout=0.4: True,
    )
    urls = connection_candidates()
    assert urls
    decoded = [decode_odbc_connect(url) or url for url in urls]
    assert all("Trusted_Connection" not in item for item in decoded)
    assert any("Authentication=SqlPassword" in item for item in decoded)
    assert any("UID=sa" in item for item in decoded)


def test_sql_auth_odbc_connects_force_uid_sa() -> None:
    from gis2dgs.input.readers.mssql_backup import sql_auth_odbc_connects

    variants = sql_auth_odbc_connects(
        host="127.0.0.1",
        port="1433",
        user="sa",
        password="Gis2dgs_Dev1!",
        drivers=("ODBC Driver 18 for SQL Server",),
    )
    assert variants
    assert all("UID=sa" in item for item in variants)
    assert all("Trusted_Connection" not in item for item in variants)
    assert any("Authentication=SqlPassword" in item for item in variants)


def test_database_url_rewrites_odbc_connect() -> None:
    from gis2dgs.input.readers.mssql_backup import (
        database_url,
        decode_odbc_connect,
        sqlalchemy_odbc_url,
    )

    source = sqlalchemy_odbc_url(
        "DRIVER={ODBC Driver 18 for SQL Server};SERVER=127.0.0.1,1433;"
        "DATABASE=master;UID=sa;PWD=x;Encrypt=yes;TrustServerCertificate=yes;"
        "Authentication=SqlPassword"
    )
    rewritten = database_url(source, "ELOR25_V1")
    raw = decode_odbc_connect(rewritten)
    assert raw is not None
    assert "DATABASE=ELOR25_V1" in raw
    assert "DATABASE=master" not in raw


def test_wait_for_docker_odbc_succeeds_with_sql_password(monkeypatch) -> None:
    import sys
    import types

    from gis2dgs.input.readers.mssql_backup import wait_for_docker_odbc

    def fake_connect(odbc, timeout=3, autocommit=True):
        if "Authentication=SqlPassword" not in odbc or "UID=sa" not in odbc:
            raise OSError("18452 untrusted domain")

        class _Conn:
            def execute(self, sql):
                return None

            def close(self):
                return None

        return _Conn()

    monkeypatch.setitem(sys.modules, "pyodbc", types.SimpleNamespace(connect=fake_connect))
    monkeypatch.setenv("GIS2DGS_MSSQL_SA_PASSWORD", "Gis2dgs_Dev1!")
    monkeypatch.setenv("GIS2DGS_MSSQL_HOST", "127.0.0.1")
    monkeypatch.setenv("GIS2DGS_MSSQL_PORT", "1433")
    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.installed_odbc_drivers",
        lambda: ("ODBC Driver 18 for SQL Server",),
    )
    result = wait_for_docker_odbc(timeout_seconds=1)
    assert result["ok"] is True
    assert result["url"]
    assert "odbc_connect=" in result["url"]


def test_execute_odbc_ddl_drains_result_sets() -> None:
    from gis2dgs.input.readers.mssql_backup import execute_odbc_ddl

    calls: list[bool] = []

    class FakeResult:
        def nextset(self):
            calls.append(True)
            return len(calls) < 2

    class FakeConnection:
        def execute(self, clause):
            return FakeResult()

    execute_odbc_ddl(FakeConnection(), "BACKUP DATABASE [x]")
    assert calls


def test_drain_odbc_cursor_stops_on_false() -> None:
    from gis2dgs.input.readers.mssql_backup import drain_odbc_cursor

    calls: list[int] = []

    class FakeCursor:
        def nextset(self):
            calls.append(1)
            return len(calls) < 3

    drain_odbc_cursor(FakeCursor())
    assert calls == [1, 1, 1]


def test_execute_odbc_query_mappings_fetches_then_drains() -> None:
    from gis2dgs.input.readers.mssql_backup import execute_odbc_query_mappings

    class FakeResult:
        def mappings(self):
            return [{"LogicalName": "data", "Type": "D"}, {"LogicalName": "log", "Type": "L"}]

        def nextset(self):
            return False

    class FakeConnection:
        def execute(self, stmt):
            return FakeResult()

    rows = execute_odbc_query_mappings(
        FakeConnection(), "RESTORE FILELISTONLY FROM DISK = N'/tmp/x.bak'"
    )
    assert rows[0]["LogicalName"] == "data"
    assert rows[1]["Type"] == "L"


def test_connection_needs_sql_reconnect_windows_auth() -> None:
    from gis2dgs.input.readers.mssql_backup import (
        connection_is_stale,
        connection_needs_sql_reconnect,
    )

    err = Exception("18452 untrusted domain integrated authentication")
    assert connection_needs_sql_reconnect(err)
    assert not connection_is_stale(err)


def test_odbc_legacy_driver_omits_trust_certificate() -> None:
    url = odbc_master_url("localhost", trusted=True, driver="SQL Server")
    assert "TrustServerCertificate" not in url
    assert "SQL+Server" in url


def test_sanitize_odbc_url_strips_trust_from_legacy_driver() -> None:
    from gis2dgs.input.readers.mssql_backup import sanitize_odbc_url

    url = (
        "mssql+pyodbc://sa:x@127.0.0.1:1433/master"
        "?driver=SQL+Server&TrustServerCertificate=yes"
    )
    cleaned = sanitize_odbc_url(url)
    assert "TrustServerCertificate" not in cleaned


def test_sqlalchemy_reader_sanitizes_legacy_mssql_uri() -> None:
    from gis2dgs.input.readers.database import SqlAlchemyInputReader

    reader = SqlAlchemyInputReader(
        "mssql+pyodbc://sa:x@127.0.0.1/master"
        "?driver=SQL+Server&TrustServerCertificate=yes"
    )
    assert "TrustServerCertificate" not in reader.uri


def test_posix_restore_paths_are_not_windows_resolved() -> None:
    assert is_server_posix_path("/var/opt/mssql/data")
    sql = restore_sql(
        "/var/opt/mssql/backup/red.bak",
        "gis2dgs_restore",
        [("data", "/var/opt/mssql/data/gis2dgs_restore.mdf")],
    )
    assert "/var/opt/mssql/backup/red.bak" in sql
    assert "/var/opt/mssql/data/gis2dgs_restore.mdf" in sql
    assert "C:" not in sql


def test_moves_from_filelist_posix_and_windows(tmp_path: Path) -> None:
    rows = [
        {"LogicalName": "red_data", "Type": "D"},
        {"LogicalName": "red_log", "Type": "L"},
    ]
    posix = _moves_from_filelist(rows, "/var/opt/mssql/data", "net")
    assert posix[0][1] == "/var/opt/mssql/data/net.mdf"
    assert posix[1][1] == "/var/opt/mssql/data/net.ldf"
    win = _moves_from_filelist(rows, str(tmp_path), "net")
    assert win[0][1].endswith("net.mdf")


def test_resolve_restore_disk_copies_into_stage(tmp_path: Path) -> None:
    source = tmp_path / "red.bak"
    source.write_bytes(b"TAPE")
    stage = tmp_path / "stage"
    disk = resolve_restore_disk(
        source,
        host_stage_dir=stage,
        server_backup_dir="/var/opt/mssql/backup",
    )
    assert disk == "/var/opt/mssql/backup/red.bak"
    assert (stage / "red.bak").read_bytes() == b"TAPE"


def test_resolve_restore_disk_keeps_local_path_without_stage(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("GIS2DGS_MSSQL_HOST_STAGE_DIR", raising=False)
    monkeypatch.delenv("GIS2DGS_MSSQL_SERVER_BACKUP_DIR", raising=False)
    source = tmp_path / "red.bak"
    source.write_bytes(b"TAPE")
    assert resolve_restore_disk(source) == str(source.resolve())


def test_resolve_restore_disk_uses_env_vars(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "net.bak"
    source.write_bytes(b"TAPE")
    stage = tmp_path / "stage"
    monkeypatch.setenv("GIS2DGS_MSSQL_HOST_STAGE_DIR", str(stage))
    monkeypatch.setenv("GIS2DGS_MSSQL_SERVER_BACKUP_DIR", "/var/opt/mssql/backup")
    disk = resolve_restore_disk(source)
    assert disk == "/var/opt/mssql/backup/net.bak"
    assert (stage / "net.bak").read_bytes() == b"TAPE"


def test_restore_data_dir_docker_uses_posix(tmp_path: Path, monkeypatch) -> None:
    backup = tmp_path / "mydb.bak"
    backup.write_bytes(b"TAPE")
    monkeypatch.setenv("GIS2DGS_MSSQL_DOCKER", "true")
    monkeypatch.setenv("GIS2DGS_MSSQL_DATA_DIRECTORY", "/var/opt/mssql/data")
    reader = MssqlBackupReader(backup, server_url="mssql+pyodbc://localhost/master")
    data_dir = reader._restore_data_dir()
    assert data_dir.startswith("/var/opt/mssql/data")
    assert "C:" not in data_dir
    assert "\\" not in data_dir


def test_restore_data_dir_docker_no_env_uses_default_posix(tmp_path: Path, monkeypatch) -> None:
    backup = tmp_path / "mydb.bak"
    backup.write_bytes(b"TAPE")
    monkeypatch.setenv("GIS2DGS_MSSQL_DOCKER", "true")
    monkeypatch.delenv("GIS2DGS_MSSQL_DATA_DIRECTORY", raising=False)
    reader = MssqlBackupReader(backup, server_url="mssql+pyodbc://localhost/master")
    data_dir = reader._restore_data_dir()
    assert data_dir.startswith("/var/opt/mssql/data/")
    assert "mydb" in data_dir
    assert "C:" not in data_dir
    assert "\\" not in data_dir


def test_restore_data_dir_no_docker_uses_windows_path(tmp_path: Path, monkeypatch) -> None:
    backup = tmp_path / "mydb.bak"
    backup.write_bytes(b"TAPE")
    monkeypatch.delenv("GIS2DGS_MSSQL_DOCKER", raising=False)
    monkeypatch.delenv("GIS2DGS_MSSQL_DATA_DIRECTORY", raising=False)
    reader = MssqlBackupReader(backup, server_url="mssql+pyodbc://localhost/master")
    data_dir = reader._restore_data_dir()
    assert not data_dir.startswith("/")


def test_restore_full_docker_scenario(tmp_path: Path, monkeypatch) -> None:
    """Simulates a full Docker restore: backup is staged, MOVE TO uses posix paths."""
    backup = tmp_path / "ELOR25_V1"
    backup.write_bytes(b"TAPE")
    stage = tmp_path / "stage"
    monkeypatch.setenv("GIS2DGS_MSSQL_DOCKER", "true")
    monkeypatch.setenv("GIS2DGS_MSSQL_HOST_STAGE_DIR", str(stage))
    monkeypatch.setenv("GIS2DGS_MSSQL_SERVER_BACKUP_DIR", "/var/opt/mssql/backup")
    monkeypatch.setenv("GIS2DGS_MSSQL_DATA_DIRECTORY", "/var/opt/mssql/data")

    statements: list[str] = []

    class Result:
        def __init__(self, stmt_str: str):
            self._stmt = stmt_str

        def mappings(self):
            return [
                {"LogicalName": "ELOR_VNR_22_APR_dat", "Type": "D"},
                {"LogicalName": "ELOR_VNR_22_APR_log", "Type": "L"},
            ]

        def fetchone(self):
            # For the sys.databases query return None → DB does not exist → no DROP needed.
            if "sys.databases" in self._stmt:
                return None
            return None

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, stmt, *args, **kwargs):
            statements.append(str(stmt))
            return Result(str(stmt))

    class FakeEngine:
        def connect(self):
            return Conn()

        def dispose(self):
            return None

    from gis2dgs.input.dataset import InputDataset

    class FakeSql:
        def __init__(self, *args, **kwargs):
            pass

        def read(self):
            return InputDataset()

    reader = MssqlBackupReader(backup, server_url="mssql+pyodbc://127.0.0.1:1433/master")
    monkeypatch.setattr(reader, "_engine", lambda url: FakeEngine())
    monkeypatch.setattr(reader, "_connect_server_url", lambda: "mssql+pyodbc://127.0.0.1:1433/master")
    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.SqlAlchemyInputReader",
        FakeSql,
    )
    reader.read()
    joined = "\n".join(statements)
    # FROM DISK must be a Linux container path
    assert "FROM DISK = N'/var/opt/mssql/backup/ELOR25_V1'" in joined
    # MOVE TO paths must be posix, not Windows
    assert "/var/opt/mssql/data/" in joined
    assert "D:\\" not in joined
    assert "C:\\" not in joined
    # Backup was staged to the host mount dir
    assert (stage / "ELOR25_V1").read_bytes() == b"TAPE"


def test_single_user_sql_guards_missing_database() -> None:
    sql = single_user_sql("gis2dgs_restore")
    assert "DB_ID" in sql
    assert "SINGLE_USER" in sql
    assert "[gis2dgs_restore]" in sql


def test_reader_restore_then_read_is_mocked(tmp_path: Path, monkeypatch) -> None:
    backup = tmp_path / "net.bak"
    backup.write_bytes(b"TAPE")
    statements: list[str] = []

    class Result:
        def __init__(self, stmt_str: str = ""):
            self._stmt = stmt_str

        def mappings(self):
            return [
                {"LogicalName": "d", "Type": "D"},
                {"LogicalName": "l", "Type": "L"},
            ]

        def fetchone(self):
            # sys.databases query → None means DB doesn't exist → no DROP.
            return None

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, stmt, *args, **kwargs):
            statements.append(str(stmt))
            return Result(str(stmt))

    class Engine:
        def connect(self):
            return Conn()

        def dispose(self):
            return None

    from gis2dgs.input.dataset import InputDataset

    dataset = InputDataset()

    class FakeSql:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        def read(self):
            return dataset

    reader = MssqlBackupReader(backup, server_url="mssql+pyodbc://localhost/master")
    monkeypatch.setattr(reader, "_engine", lambda url: Engine())
    monkeypatch.setattr(reader, "_connect_server_url", lambda: "mssql+pyodbc://localhost/master")
    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.SqlAlchemyInputReader",
        FakeSql,
    )
    assert reader.read() is dataset
    joined = "\n".join(statements)
    assert "RESTORE FILELISTONLY" in joined
    assert "RESTORE DATABASE" in joined
    # _drop_db_if_exists queries sys.databases first; RESTORE follows.
    assert "sys.databases" in joined


def test_docker_compose_does_not_commit_secrets() -> None:
    root = Path(__file__).resolve().parents[3]
    compose = (root / "docker-compose.mssql.yml").read_text(encoding="utf-8")
    assert "${GIS2DGS_MSSQL_SA_PASSWORD}" in compose
    assert "mcr.microsoft.com/mssql/server:2022-CU16-ubuntu-22.04" in compose
    assert "./output/mssql/backup:/var/opt/mssql/backup" in compose
    assert "MSSQL_SA_PASSWORD: ${GIS2DGS_MSSQL_SA_PASSWORD}" in compose
    script = (root / "scripts" / "ensure_mssql.ps1").read_text(encoding="utf-8")
    assert "docker compose" in script
    assert "GIS2DGS_MSSQL_SA_PASSWORD" in script
    assert "Ensure-MssqlImage" in script
    assert "--pull" in script


def _executed_sqls(conn: MagicMock) -> list[str]:
    """Extract the SQL text from all calls to conn.execute."""
    sqls = []
    for c in conn.execute.call_args_list:
        # First positional arg is a SQLAlchemy text() object; use its .text attribute.
        stmt = c.args[0] if c.args else None
        if stmt is not None:
            sqls.append(getattr(stmt, "text", str(stmt)))
    return sqls


def test_drop_db_if_exists_when_restoring_state() -> None:
    """RESTORING state: must DROP directly without ALTER DATABASE SET SINGLE_USER."""
    conn = MagicMock()
    row_mock = MagicMock()
    row_mock.__getitem__ = lambda self, i: "RESTORING"
    conn.execute.return_value.fetchone.return_value = row_mock

    _drop_db_if_exists(conn, "mydb")

    sqls = _executed_sqls(conn)
    assert any("sys.databases" in s for s in sqls), "Should query sys.databases"
    assert any("DROP DATABASE" in s for s in sqls), "Should issue DROP DATABASE"
    assert not any("SINGLE_USER" in s for s in sqls), "Must NOT call SET SINGLE_USER"


def test_drop_db_if_exists_when_online_state() -> None:
    """ONLINE state: must do SET SINGLE_USER first, then DROP DATABASE."""
    conn = MagicMock()
    row_mock = MagicMock()
    row_mock.__getitem__ = lambda self, i: "ONLINE"
    conn.execute.return_value.fetchone.return_value = row_mock

    _drop_db_if_exists(conn, "mydb")

    sqls = _executed_sqls(conn)
    assert any("sys.databases" in s for s in sqls)
    assert any("SINGLE_USER" in s for s in sqls), "Should call SET SINGLE_USER for ONLINE"
    assert any("DROP DATABASE" in s for s in sqls)


def test_drop_db_if_exists_when_not_exists() -> None:
    """DB not found: must not execute any DDL."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None

    _drop_db_if_exists(conn, "nonexistent")

    sqls = _executed_sqls(conn)
    assert conn.execute.call_count == 1
    assert any("sys.databases" in s for s in sqls), "Should query sys.databases"
    assert not any("DROP" in s for s in sqls if "sys.databases" not in s)
    assert not any("SINGLE_USER" in s for s in sqls)


def test_mssql_backup_example_project_is_complete() -> None:
    root = Path(__file__).resolve().parents[3]
    example = root / "examples" / "mssql_backup"
    payload = yaml.safe_load((example / "project.yaml").read_text(encoding="utf-8"))
    source = payload["inputs"]["sources"][0]
    assert source["kind"] == "mssql_backup"
    assert source["uri"] == "$GIS2DGS_MSSQL_BACKUP"
    for name in (
        "mapping.yaml",
        "validation.yaml",
        "electrical_library.yaml",
        "powerfactory_mapping.yaml",
        "dgs_mapping.yaml",
    ):
        assert (example / "config" / name).is_file()
    mapping = yaml.safe_load((example / "config" / "mapping.yaml").read_text(encoding="utf-8"))
    assert mapping["buses"]["source"] == "buses"
    assert mapping["lines"]["source"] == "lines"
    from gis2dgs.config import load_project_config

    project = load_project_config(example / "project.yaml")
    assert project.inputs.sources[0].kind == "mssql_backup"
    assert project.mapping.name == "mapping.yaml"
