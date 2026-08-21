from __future__ import annotations

import os
import re
import shutil
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, unquote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection as SAConnection
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.sql.elements import TextClause

from ..dataset import InputDataset
from ..exceptions import InputDependencyError, InputError
from .database import SqlAlchemyInputReader

MISSING_SERVER_ERROR = (
    "Para convertir un backup SQL Server (.bak) a DGS hay que restaurarlo en SQL Server. "
    "El restore ya está implementado. Falta un proceso SQL Server accesible. "
    "Ejecute scripts/ensure_mssql.ps1 (detecta LocalDB/Express/localhost o arranca Docker) "
    "o configure GIS2DGS_MSSQL_URL hacia master, por ejemplo "
    "mssql+pyodbc://usuario:clave@servidor/master?driver=ODBC+Driver+17+for+SQL+Server."
)

_PREFERRED_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "SQL Server",
)


def sql_literal(value: str) -> str:
    return "N'" + value.replace("'", "''") + "'"


def sql_ident(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


_ODBC_RESULT_SET_CAP = 256


def _statement_sql(statement: str | TextClause) -> str:
    if isinstance(statement, str):
        return statement
    compiled = getattr(statement, "text", None)
    if compiled:
        return str(compiled)
    return str(statement)


def _dbapi_connection(connection: Any) -> Any | None:
    """Unwrap a real SQLAlchemy Connection to the pyodbc DBAPI connection."""

    if not isinstance(connection, SAConnection):
        return None
    raw = connection.connection
    return getattr(raw, "dbapi_connection", None) or raw


def drain_odbc_cursor(cursor: Any, *, max_sets: int = _ODBC_RESULT_SET_CAP) -> None:
    """Drain TDS info/done packets after BACKUP/RESTORE.

    SQL Server sends STATS progress as extra ODBC result sets. Closing the
    cursor before SQLMoreResults finishes aborts the operation silently
    (pyodbc issue 471; Microsoft TDS / ODBC SQLMoreResults).
    """

    for _ in range(max_sets):
        try:
            more = cursor.nextset()
        except Exception:
            return
        if not more:
            return


def drain_sqlalchemy_result(result: Any) -> None:
    """Fallback drain when only a SQLAlchemy Result is available."""

    nxt = getattr(result, "nextset", None)
    if not callable(nxt):
        return
    for _ in range(_ODBC_RESULT_SET_CAP):
        try:
            more = nxt()
        except Exception:
            return
        if more is True:
            continue
        return


def execute_odbc_ddl(connection: Any, statement: str | TextClause) -> None:
    """Run BACKUP/RESTORE/ALTER DATABASE to completion (autocommit + nextset)."""

    sql = _statement_sql(statement)
    dbapi = _dbapi_connection(connection)
    if dbapi is None:
        clause = text(sql) if isinstance(statement, str) else statement
        drain_sqlalchemy_result(connection.execute(clause))
        return
    cursor = dbapi.cursor()
    try:
        cursor.execute(sql)
        drain_odbc_cursor(cursor)
    finally:
        cursor.close()


def execute_odbc_query_mappings(connection: Any, statement: str) -> list[dict[str, Any]]:
    """Fetch one result set then drain remaining ODBC packets (FILELISTONLY)."""

    dbapi = _dbapi_connection(connection)
    if dbapi is None:
        return [dict(row) for row in connection.execute(text(statement)).mappings()]
    cursor = dbapi.cursor()
    try:
        cursor.execute(statement)
        columns = [col[0] for col in (cursor.description or ())]
        rows = cursor.fetchall() if columns else []
        drain_odbc_cursor(cursor)
        return [dict(zip(columns, row, strict=False)) for row in rows]
    finally:
        cursor.close()


def sanitize_database_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name.strip()) or "gis2dgs_restore"
    if cleaned[0].isdigit():
        cleaned = "db_" + cleaned
    return cleaned[:120]


def is_server_posix_path(path: str | Path) -> bool:
    text = str(path).replace("\\", "/")
    return text.startswith("/") and not text.startswith("//")


def physical_path_text(path: str | Path) -> str:
    text = str(path)
    if is_server_posix_path(text):
        return text.replace("\\", "/")
    return str(Path(text).resolve())


def backup_disk_text(backup_path: Path | str) -> str:
    if isinstance(backup_path, Path):
        return str(backup_path.resolve())
    if is_server_posix_path(backup_path):
        return str(backup_path).replace("\\", "/")
    return str(Path(backup_path).resolve())


def filelist_sql(backup_path: Path | str) -> str:
    return f"RESTORE FILELISTONLY FROM DISK = {sql_literal(backup_disk_text(backup_path))}"


def restore_sql(
    backup_path: Path | str,
    database: str,
    moves: list[tuple[str, Path | str]],
    *,
    replace: bool = True,
) -> str:
    clauses = [
        f"MOVE {sql_literal(logical)} TO {sql_literal(physical_path_text(physical))}"
        for logical, physical in moves
    ]
    if replace:
        clauses.append("REPLACE")
    clauses.append("RECOVERY")
    return (
        f"RESTORE DATABASE {sql_ident(database)} FROM DISK = "
        f"{sql_literal(backup_disk_text(backup_path))} WITH {', '.join(clauses)}"
    )


def single_user_sql(database: str) -> str:
    return (
        f"IF DB_ID({sql_literal(database)}) IS NOT NULL "
        f"ALTER DATABASE {sql_ident(database)} SET SINGLE_USER WITH ROLLBACK IMMEDIATE"
    )


# States where ALTER DATABASE SET SINGLE_USER is not permitted by SQL Server.
_NO_SINGLE_USER_STATES = frozenset(
    {"RESTORING", "RECOVERING", "RECOVERY_PENDING", "SUSPECT", "EMERGENCY"}
)


def _drop_db_if_exists(conn: Any, db_name: str) -> None:
    """Drop *db_name* robustly, handling every possible database state.

    SQL Server forbids ``ALTER DATABASE … SET SINGLE_USER`` when the database
    is in RESTORING/RECOVERING/SUSPECT/EMERGENCY state (error 5052).  In those
    states we issue ``DROP DATABASE`` directly — SQL Server allows it even for
    a database stuck in RESTORING.  For ONLINE (or any other "normal") state we
    first kick all connections via SINGLE_USER and then drop.

    The *conn* must be on an AUTOCOMMIT connection; DDL like ALTER/DROP DATABASE
    cannot run inside an explicit transaction.
    """
    row = conn.execute(
        text(
            "SELECT state_desc FROM sys.databases WHERE name = :n"
        ),
        {"n": db_name},
    ).fetchone()

    if row is None:
        return  # Database does not exist — nothing to do.

    state = str(row[0]).upper()

    if state in _NO_SINGLE_USER_STATES:
        # Cannot ALTER DATABASE in this state; DROP directly.
        execute_odbc_ddl(conn, f"DROP DATABASE {sql_ident(db_name)}")
    else:
        # ONLINE or other "normal" state: evict connections first.
        execute_odbc_ddl(
            conn,
            f"ALTER DATABASE {sql_ident(db_name)} SET SINGLE_USER WITH ROLLBACK IMMEDIATE",
        )
        execute_odbc_ddl(conn, f"DROP DATABASE {sql_ident(db_name)}")


def database_url(server_url: str, database: str) -> str:
    odbc = decode_odbc_connect(server_url)
    if odbc is not None:
        if re.search(r"(?i)DATABASE=", odbc):
            odbc = re.sub(r"(?i)DATABASE=[^;]*", f"DATABASE={database}", odbc)
        else:
            odbc = odbc.rstrip(";") + f";DATABASE={database}"
        return sqlalchemy_odbc_url(odbc)
    url = make_url(server_url)
    return str(url.set(database=database))


def encode_odbc_driver(name: str) -> str:
    return name.replace(" ", "+")


def driver_allows_trust_certificate(driver: str) -> bool:
    """Legacy 'SQL Server' rejects TrustServerCertificate; ODBC 13/17/18 accept it."""

    name = driver.replace("+", " ").strip().lower()
    return any(
        token in name
        for token in ("odbc driver 13", "odbc driver 17", "odbc driver 18")
    )


def connection_is_windows_auth_rejected(exc: BaseException | str) -> bool:
    msg = str(exc).lower()
    return (
        "18452" in msg
        or "untrusted domain" in msg
        or "integrated authentication" in msg
    )


def connection_is_stale(exc: BaseException) -> bool:
    """True for sa login failure or an invalid ODBC attribute on the URL."""

    if connection_is_windows_auth_rejected(exc):
        return False
    msg = str(exc).lower()
    return (
        "18456" in msg
        or "login failed" in msg
        or "invalid connection string" in msg
        or "atributo de cadena" in msg
    )


def connection_needs_sql_reconnect(exc: BaseException) -> bool:
    """True when the client used Windows auth or the sa/ODBC URL is stale."""

    return connection_is_stale(exc) or connection_is_windows_auth_rejected(exc)


def sanitize_odbc_url(url: str) -> str:
    """Drop TrustServerCertificate/Encrypt when the selected driver cannot use them."""

    if not url.startswith("mssql"):
        return url
    odbc = decode_odbc_connect(url)
    if odbc is not None:
        driver = _driver_from_odbc(odbc)
        if driver and not driver_allows_trust_certificate(driver):
            odbc = _strip_legacy_odbc_keywords(odbc)
        return sqlalchemy_odbc_url(odbc)
    try:
        parsed = make_url(url)
    except Exception:
        return url
    query = dict(parsed.query)
    driver = str(query.get("driver", "")).replace("+", " ")
    if driver and not driver_allows_trust_certificate(driver):
        query = {
            key: value
            for key, value in query.items()
            if key.lower() not in {"trustservercertificate", "encrypt", "authentication"}
        }
        return str(parsed.set(query=query))
    return str(parsed)


def installed_odbc_drivers() -> tuple[str, ...]:
    try:
        import pyodbc
    except ImportError:
        return ()
    found = [name for name in pyodbc.drivers() if "SQL Server" in name]
    preferred = [name for name in _PREFERRED_DRIVERS if name in found]
    extra = [name for name in found if name not in preferred]
    return tuple(preferred + extra)


def has_modern_odbc_driver(drivers: tuple[str, ...] | None = None) -> bool:
    names = drivers if drivers is not None else installed_odbc_drivers()
    return any(driver_allows_trust_certificate(name) for name in names)


def escape_odbc_password(password: str) -> str:
    if any(char in password for char in ";{}"):
        return "{" + password.replace("}", "}}") + "}"
    return password


def sqlalchemy_odbc_url(odbc: str) -> str:
    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc)


def decode_odbc_connect(url: str) -> str | None:
    if "odbc_connect=" not in url.lower():
        return None
    try:
        parsed = make_url(url)
    except Exception:
        return None
    raw = parsed.query.get("odbc_connect")
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        raw = raw[0]
    return unquote_plus(str(raw))


def _driver_from_odbc(odbc: str) -> str:
    for part in odbc.split(";"):
        if part.upper().startswith("DRIVER="):
            return part.split("=", 1)[1].strip().strip("{}")
    return ""


def _strip_legacy_odbc_keywords(odbc: str) -> str:
    drop = {"trustservercertificate", "encrypt", "authentication"}
    kept: list[str] = []
    for part in odbc.split(";"):
        if not part:
            continue
        key = part.split("=", 1)[0].strip().lower()
        if key not in drop:
            kept.append(part)
    return ";".join(kept)


def sql_auth_odbc_connects(
    *,
    host: str,
    port: str,
    user: str,
    password: str,
    drivers: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Raw ODBC strings that force SQL authentication (never Windows/SSPI)."""

    names = drivers if drivers is not None else installed_odbc_drivers()
    if not names:
        names = ("SQL Server",)
    pwd = escape_odbc_password(password)
    servers: list[str] = [f"{host},{port}"]
    if host == "127.0.0.1":
        servers.append(f"localhost,{port}")
    elif host.lower() == "localhost":
        servers.append(f"127.0.0.1,{port}")
    unique_servers: list[str] = []
    for server in servers:
        if server not in unique_servers:
            unique_servers.append(server)
    connects: list[str] = []
    for driver in names:
        braced = "{" + driver + "}"
        for server in unique_servers:
            base = (
                f"DRIVER={braced};SERVER={server};DATABASE=master;"
                f"UID={user};PWD={pwd}"
            )
            if driver_allows_trust_certificate(driver):
                connects.append(
                    base
                    + ";Encrypt=yes;TrustServerCertificate=yes;"
                    + "Authentication=SqlPassword"
                )
                connects.append(base + ";Encrypt=yes;TrustServerCertificate=yes")
                connects.append(
                    base
                    + ";Encrypt=no;TrustServerCertificate=yes;"
                    + "Authentication=SqlPassword"
                )
            else:
                connects.append(base)
    unique: list[str] = []
    for item in connects:
        if item not in unique:
            unique.append(item)
    return tuple(unique)


def _pyodbc_connect(odbc: str, *, timeout: int = 3) -> None:
    import pyodbc

    connection = pyodbc.connect(odbc, timeout=timeout, autocommit=True)
    try:
        connection.execute("SELECT 1")
    finally:
        connection.close()


def odbc_master_url(
    host: str,
    *,
    trusted: bool = True,
    user: str | None = None,
    password: str | None = None,
    driver: str,
) -> str:
    encoded = encode_odbc_driver(driver)
    query = f"driver={encoded}"
    if driver_allows_trust_certificate(driver):
        query += "&TrustServerCertificate=yes"
        if not trusted:
            # Domain-joined Windows otherwise ignores UID/PWD (SQL error 18452).
            query += "&Authentication=SqlPassword"
    if trusted:
        return f"mssql+pyodbc://{host}/master?{query}&Trusted_Connection=yes"
    if not user or password is None:
        raise ValueError("SQL authentication requires user and password.")
    auth = f"{quote_plus(user)}:{quote_plus(password)}"
    return f"mssql+pyodbc://{auth}@{host}/master?{query}"


def docker_master_url(
    *,
    password: str | None = None,
    host: str | None = None,
    port: str | None = None,
    driver: str | None = None,
) -> str | None:
    secret = password if password is not None else os.environ.get("GIS2DGS_MSSQL_SA_PASSWORD", "")
    if not secret.strip():
        return None
    listen = host or os.environ.get("GIS2DGS_MSSQL_HOST", "127.0.0.1")
    tcp_port = port or os.environ.get("GIS2DGS_MSSQL_PORT", "1433")
    names = installed_odbc_drivers()
    chosen = driver or (names[0] if names else "SQL Server")
    variants = sql_auth_odbc_connects(
        host=listen,
        port=str(tcp_port),
        user="sa",
        password=secret,
        drivers=(chosen,),
    )
    return sqlalchemy_odbc_url(variants[0])


def _tcp_open(host: str, port: int, timeout: float = 0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _uses_windows_auth(url: str) -> bool:
    text = decode_odbc_connect(url) or url
    lowered = text.lower().replace(" ", "")
    return "trusted_connection=yes" in lowered or "integratedsecurity=yes" in lowered


def connection_candidates(explicit_url: str | None = None) -> tuple[str, ...]:
    urls: list[str] = []
    docker_url = docker_master_url()
    docker_only = os.environ.get("GIS2DGS_MSSQL_DOCKER", "").strip().lower() == "true"
    if explicit_url:
        cleaned = sanitize_odbc_url(explicit_url)
        if not (docker_only and _uses_windows_auth(cleaned)):
            urls.append(cleaned)
    env_url = os.environ.get("GIS2DGS_MSSQL_URL", "").strip()
    if env_url:
        cleaned = sanitize_odbc_url(env_url)
        if cleaned not in urls and not (docker_only and _uses_windows_auth(cleaned)):
            urls.append(cleaned)
    if docker_url and docker_url not in urls:
        urls.append(docker_url)
    if docker_only:
        return tuple(urls)
    drivers = installed_odbc_drivers()[:1]
    hosts: list[str] = []
    if _tcp_open("127.0.0.1", int(os.environ.get("GIS2DGS_MSSQL_PORT", "1433"))):
        hosts.extend(("localhost", "127.0.0.1"))
    instance = os.environ.get("GIS2DGS_MSSQL_INSTANCE", "").strip()
    if instance:
        hosts.append(instance)
    if shutil.which("sqllocaldb"):
        hosts.append(r"(localdb)\MSSQLLocalDB")
    for driver in drivers:
        for host in hosts:
            url = odbc_master_url(host, trusted=True, driver=driver)
            if url not in urls:
                urls.append(url)
    return tuple(urls)


def resolve_restore_disk(
    local_path: Path,
    *,
    host_stage_dir: str | Path | None = None,
    server_backup_dir: str | None = None,
) -> str:
    """Return the DISK path SQL Server must use, staging the file when Docker-mounted."""

    stage = host_stage_dir or os.environ.get("GIS2DGS_MSSQL_HOST_STAGE_DIR", "").strip()
    server_dir = server_backup_dir or os.environ.get(
        "GIS2DGS_MSSQL_SERVER_BACKUP_DIR", ""
    ).strip()
    if not stage or not server_dir:
        return str(local_path.resolve())
    host_dir = Path(stage)
    host_dir.mkdir(parents=True, exist_ok=True)
    staged = host_dir / local_path.name
    if staged.resolve() != local_path.resolve():
        shutil.copy2(local_path, staged)
    server_root = str(server_dir).replace("\\", "/").rstrip("/")
    return f"{server_root}/{local_path.name}"


@dataclass(frozen=True, slots=True)
class ProbeStatus:
    url: str | None
    stale_connection: bool = False
    error: str | None = None


def probe_sql_auth_variants(*, require_open_port: bool = True) -> ProbeStatus:
    """Try sa UID/PWD ODBC strings; never Windows integrated authentication."""

    password = os.environ.get("GIS2DGS_MSSQL_SA_PASSWORD", "").strip()
    if not password:
        return ProbeStatus(url=None)
    host = os.environ.get("GIS2DGS_MSSQL_HOST", "127.0.0.1")
    port = os.environ.get("GIS2DGS_MSSQL_PORT", "1433")
    if require_open_port and not _tcp_open(host, int(port)):
        return ProbeStatus(url=None)
    last_error: str | None = None
    stale = False
    for odbc in sql_auth_odbc_connects(
        host=host,
        port=str(port),
        user="sa",
        password=password,
    ):
        try:
            _pyodbc_connect(odbc, timeout=3)
            return ProbeStatus(url=sqlalchemy_odbc_url(odbc))
        except Exception as exc:
            last_error = str(exc)
            if connection_is_stale(exc):
                stale = True
            continue
    return ProbeStatus(url=None, stale_connection=stale, error=last_error)


def wait_for_docker_odbc(*, timeout_seconds: int = 120) -> dict[str, Any]:
    """Retry sa ODBC variants until SQL Server in Docker accepts the login."""

    deadline = time.monotonic() + max(1, int(timeout_seconds))
    last = ProbeStatus(url=None)
    while time.monotonic() < deadline:
        last = probe_sql_auth_variants(require_open_port=False)
        if last.url:
            os.environ["GIS2DGS_MSSQL_URL"] = last.url
            os.environ["GIS2DGS_MSSQL_DOCKER"] = "true"
            return {
                "ok": True,
                "url": last.url,
                "error": None,
                "restore_implemented": True,
                "ensure_script": "scripts/ensure_mssql.ps1",
                "stale_connection": False,
                "odbc_drivers": list(installed_odbc_drivers()),
                "modern_odbc": has_modern_odbc_driver(),
            }
        time.sleep(2)
    return {
        "ok": False,
        "url": None,
        "error": last.error or MISSING_SERVER_ERROR,
        "restore_implemented": True,
        "ensure_script": "scripts/ensure_mssql.ps1",
        "stale_connection": last.stale_connection,
        "odbc_drivers": list(installed_odbc_drivers()),
        "modern_odbc": has_modern_odbc_driver(),
    }


def probe_status(explicit_url: str | None = None) -> ProbeStatus:
    sql_auth = probe_sql_auth_variants()
    if sql_auth.url:
        return sql_auth
    stale = sql_auth.stale_connection
    last_error = sql_auth.error
    for url in connection_candidates(explicit_url):
        if _uses_windows_auth(url) and os.environ.get("GIS2DGS_MSSQL_SA_PASSWORD", "").strip():
            continue
        try:
            engine = create_engine(
                sanitize_odbc_url(url),
                isolation_level="AUTOCOMMIT",
                connect_args={"timeout": 2},
            )
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            engine.dispose()
            return ProbeStatus(url=sanitize_odbc_url(url))
        except Exception as exc:
            if not connection_is_windows_auth_rejected(exc):
                last_error = str(exc)
            if connection_is_stale(exc):
                stale = True
            continue
    return ProbeStatus(url=None, stale_connection=stale, error=last_error)


def probe_sql_server(explicit_url: str | None = None) -> str | None:
    return probe_status(explicit_url).url


def probe_report(explicit_url: str | None = None) -> dict[str, Any]:
    status = probe_status(explicit_url)
    return {
        "ok": status.url is not None,
        "url": status.url,
        "restore_implemented": True,
        "ensure_script": "scripts/ensure_mssql.ps1",
        "error": None if status.url else (status.error or MISSING_SERVER_ERROR),
        "stale_connection": status.stale_connection,
        "odbc_drivers": list(installed_odbc_drivers()),
        "modern_odbc": has_modern_odbc_driver(),
    }


class MssqlBackupReader:
    """Restore a SQL Server backup file and read its tables as InputDataset."""

    def __init__(
        self,
        path: Path,
        *,
        source_id: str | None = None,
        server_url: str | None = None,
        restore_database: str | None = None,
        data_directory: str | Path | None = None,
        replace: bool = True,
        skip_restore: bool = False,
        tables: tuple[str, ...] | None = None,
        queries: dict[str, str] | None = None,
        spatial_queries: dict[str, str] | None = None,
        geometry_column: str = "geometry",
        aliases: dict[str, str] | None = None,
        connect_args: dict[str, Any] | None = None,
        sample_rows: int | None = None,
        compact: bool = True,
        copy_frame: bool = False,
        host_stage_dir: str | Path | None = None,
        server_backup_dir: str | None = None,
    ) -> None:
        self.path = Path(path)
        self.source_id = source_id
        self.server_url = server_url or os.environ.get("GIS2DGS_MSSQL_URL")
        self.restore_database = sanitize_database_name(
            restore_database or self.path.stem or "gis2dgs_restore"
        )
        env_data = os.environ.get("GIS2DGS_MSSQL_DATA_DIRECTORY", "").strip()
        chosen_data = data_directory if data_directory is not None else (env_data or None)
        self.data_directory = str(chosen_data) if chosen_data else None
        self.replace = replace
        self.skip_restore = skip_restore
        self.tables = tuple(tables) if tables is not None else None
        self.queries = dict(queries or {})
        self.spatial_queries = dict(spatial_queries or {})
        self.geometry_column = geometry_column
        self.aliases = dict(aliases or {})
        self.connect_args = dict(connect_args or {})
        self.sample_rows = sample_rows
        self.compact = compact
        self.copy_frame = copy_frame
        self.host_stage_dir = host_stage_dir
        self.server_backup_dir = server_backup_dir

    def read(self) -> InputDataset:
        if not self.path.exists():
            raise InputError(f"SQL Server backup does not exist: {self.path}")
        server_url = self._connect_server_url()
        if not self.skip_restore:
            self._restore(server_url)
        restored_url = database_url(server_url, self.restore_database)
        return SqlAlchemyInputReader(
            restored_url,
            source_id=self.source_id,
            tables=self.tables,
            queries=self.queries or None,
            spatial_queries=self.spatial_queries or None,
            geometry_column=self.geometry_column,
            aliases=self.aliases or None,
            connect_args=self.connect_args or None,
            sample_rows=self.sample_rows,
            compact=self.compact,
            copy_frame=self.copy_frame,
        ).read()

    def _connect_server_url(self) -> str:
        from gis2dgs.input.mssql_ensure import ensure_sql_server

        return ensure_sql_server(self.server_url)

    def _restore(self, server_url: str) -> None:
        engine = self._engine(server_url)
        disk = resolve_restore_disk(
            self.path,
            host_stage_dir=self.host_stage_dir,
            server_backup_dir=self.server_backup_dir,
        )
        data_dir = self._restore_data_dir()
        try:
            with engine.connect() as connection:
                rows = execute_odbc_query_mappings(connection, filelist_sql(disk))
                if not rows:
                    raise InputError(f"El backup no declaró archivos lógicos: {self.path}")
                moves = _moves_from_filelist(rows, data_dir, self.restore_database)
                _drop_db_if_exists(connection, self.restore_database)
                statement = restore_sql(
                    disk,
                    self.restore_database,
                    moves,
                    replace=self.replace,
                )
                execute_odbc_ddl(connection, statement)
        except InputError:
            raise
        except Exception as exc:
            raise InputError(
                "No se pudo restaurar el backup en SQL Server. "
                f"Compruebe permisos sobre {self.path} y GIS2DGS_MSSQL_URL. "
                "Si usa Docker, ejecute scripts/ensure_mssql.ps1 para montar "
                "output/mssql/backup. Detalle: "
                f"{exc}"
            ) from exc
        finally:
            engine.dispose()

    def _restore_data_dir(self) -> str:
        is_docker = os.environ.get("GIS2DGS_MSSQL_DOCKER", "").strip().lower() == "true"
        if self.data_directory:
            directory = self.data_directory
        elif is_docker:
            # Docker Linux container: use the server-side data directory.
            # Append the database name as a subdirectory so each restore is isolated.
            server_data = os.environ.get(
                "GIS2DGS_MSSQL_DATA_DIRECTORY", "/var/opt/mssql/data"
            ).rstrip("/")
            directory = f"{server_data}/{self.restore_database}"
        else:
            directory = str(
                (Path("output") / "mssql_restore" / self.restore_database).resolve()
            )
        if not is_server_posix_path(directory):
            Path(directory).mkdir(parents=True, exist_ok=True)
        return directory

    def _engine(self, url: str) -> Engine:
        try:
            return create_engine(
                sanitize_odbc_url(url),
                isolation_level="AUTOCOMMIT",
                connect_args=self.connect_args,
            )
        except ModuleNotFoundError as exc:
            raise InputDependencyError(
                "SQL Server backup restore requires pyodbc and an ODBC Driver for SQL Server."
            ) from exc
        except Exception as extra:
            raise InputError(f"Unable to create SQL Server engine: {extra}") from extra


def _moves_from_filelist(
    rows: list[Any],
    data_dir: str,
    database: str,
) -> list[tuple[str, str]]:
    moves: list[tuple[str, str]] = []
    data_index = 0
    log_index = 0
    posix = is_server_posix_path(data_dir)
    root = data_dir.rstrip("/\\")
    for row in rows:
        logical = str(row["LogicalName"] if "LogicalName" in row else row["logicalname"])
        file_type = str(row.get("Type") or row.get("type") or "D").upper()
        if file_type.startswith("L"):
            suffix = ".ldf" if log_index == 0 else f"_{log_index}.ldf"
            log_index += 1
            filename = f"{database}{suffix}"
        else:
            suffix = ".mdf" if data_index == 0 else f"_{data_index}.ndf"
            data_index += 1
            filename = f"{database}{suffix}"
        if posix:
            physical = f"{root}/{filename}"
        else:
            physical = str(Path(root) / filename)
        moves.append((logical, physical))
    return moves
