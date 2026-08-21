"""Ensure a reachable SQL Server instance for .bak restore (local, LocalDB, or Docker)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from gis2dgs.input.exceptions import InputError

_MSSQL_ENV_KEYS = (
    "GIS2DGS_MSSQL_URL",
    "GIS2DGS_MSSQL_HOST_STAGE_DIR",
    "GIS2DGS_MSSQL_SERVER_BACKUP_DIR",
    "GIS2DGS_MSSQL_DATA_DIRECTORY",
    "GIS2DGS_MSSQL_PORT",
    "GIS2DGS_MSSQL_HOST",
    "GIS2DGS_MSSQL_SA_PASSWORD",
    "GIS2DGS_MSSQL_INSTANCE",
    "GIS2DGS_MSSQL_DOCKER",
)

_ENSURE_EXIT_MESSAGES = {
    2: (
        "Docker no está instalado. Instale Docker Desktop o SQL Server Express/LocalDB, "
        "o configure GIS2DGS_MSSQL_URL hacia master."
    ),
    3: (
        "Docker está instalado pero el motor no quedó listo a tiempo. "
        "Abra Docker Desktop, espere a que diga Running y pulse Ejecutar de nuevo."
    ),
    4: (
        "El contenedor SQL Server arrancó pero aún no acepta conexiones ODBC. "
        "Instale Microsoft ODBC Driver 17/18 for SQL Server, espere unos segundos "
        "y pulse Ejecutar de nuevo."
    ),
}


def find_repo_root() -> Path:
    """Return repository root (directory containing scripts/ensure_mssql.ps1)."""

    candidates: list[Path] = [Path.cwd()]
    here = Path(__file__).resolve()
    candidates.extend(here.parents)
    for base in candidates:
        if (base / "scripts" / "ensure_mssql.ps1").is_file():
            return base
    return Path.cwd()


def session_env_path(root: Path | None = None) -> Path:
    base = root or find_repo_root()
    return base / "output" / "mssql" / "session.env.ps1"


def apply_session_env(path: Path | None = None) -> bool:
    """Load GIS2DGS_MSSQL_* variables from output/mssql/session.env.ps1 into os.environ."""

    session = path or session_env_path()
    if not session.is_file():
        return False
    text = session.read_text(encoding="utf-8")
    pattern = re.compile(r"\$env:(\w+)\s*=\s*['\"]([^'\"]*)['\"]")
    for match in pattern.finditer(text):
        os.environ[match.group(1)] = match.group(2)
    return True


def load_sa_password(*, session_file: Path | None = None, root: Path | None = None) -> str | None:
    """Load sa password from output/mssql/.sa_password (never committed)."""

    if session_file is not None:
        path = Path(session_file).parent / ".sa_password"
    else:
        path = (root or find_repo_root()) / "output" / "mssql" / ".sa_password"
    if not path.is_file():
        return None
    secret = path.read_text(encoding="utf-8").strip()
    if not secret:
        return None
    os.environ["GIS2DGS_MSSQL_SA_PASSWORD"] = secret
    return secret


def _looks_like_local_sa_url(url: str) -> bool:
    from sqlalchemy.engine import make_url

    try:
        parsed = make_url(url)
    except Exception:
        lowered = url.lower()
        has_sa = "sa:" in lowered or "sa%" in lowered
        local = "127.0.0.1" in url or "localhost" in lowered
        return has_sa and local
    host = str(parsed.host or "").lower()
    user = str(parsed.username or "").lower()
    return user == "sa" and host in {"127.0.0.1", "localhost"}


def _sync_local_sa_connection_url() -> None:
    """Rebuild a local Docker sa URL from .sa_password and the installed ODBC driver."""

    from gis2dgs.input.readers.mssql_backup import docker_master_url, sanitize_odbc_url

    current = os.environ.get("GIS2DGS_MSSQL_URL", "").strip()
    if current:
        os.environ["GIS2DGS_MSSQL_URL"] = sanitize_odbc_url(current)
        current = os.environ["GIS2DGS_MSSQL_URL"]
    docker_url = docker_master_url()
    if not docker_url:
        return
    docker_flag = os.environ.get("GIS2DGS_MSSQL_DOCKER", "").strip().lower() == "true"
    if docker_flag or not current or _looks_like_local_sa_url(current):
        os.environ["GIS2DGS_MSSQL_URL"] = docker_url


def prepare_mssql_environment(path: Path | None = None) -> bool:
    """Load session env, .sa_password, and rewrite a stale local sa ODBC URL."""

    session = path or session_env_path()
    loaded = apply_session_env(session)
    load_sa_password(session_file=session)
    _sync_local_sa_connection_url()
    return loaded


def resolve_runtime_mssql_url(uri: str) -> str:
    """Sanitize *uri* and, for local sa, replace credentials with the live session URL."""

    from sqlalchemy.engine import make_url

    from gis2dgs.input.readers.mssql_backup import database_url, sanitize_odbc_url

    prepare_mssql_environment()
    cleaned = sanitize_odbc_url(uri)
    env_url = sanitize_odbc_url(os.environ.get("GIS2DGS_MSSQL_URL", "").strip())
    if not env_url or not _looks_like_local_sa_url(cleaned):
        return cleaned
    try:
        parsed = make_url(cleaned)
    except Exception:
        return cleaned
    database = parsed.database or "master"
    return database_url(env_url, database)


def run_ensure_script(*, quiet: bool = True, timeout: int = 360) -> int:
    """Invoke scripts/ensure_mssql.ps1 (canonical Docker/local provisioner)."""

    root = find_repo_root()
    script = root / "scripts" / "ensure_mssql.ps1"
    if not script.is_file():
        raise InputError(f"No se encontró el provisionador SQL Server: {script}")
    args = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
    ]
    if quiet:
        args.append("-Quiet")
    result = subprocess.run(
        args,
        cwd=str(root),
        timeout=timeout,
        check=False,
    )
    prepare_mssql_environment(session_env_path(root))
    return int(result.returncode)


_CONTAINER_NAME = "gis2dgs-mssql"


def _is_login_failed(exc: Exception) -> bool:
    """Return True for sa 18456 or an invalid ODBC connection-string attribute."""

    from gis2dgs.input.readers.mssql_backup import connection_is_stale

    return connection_is_stale(exc)


def _docker_container_present() -> bool:
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={_CONTAINER_NAME}",
                "--format",
                "{{.Names}}",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    return _CONTAINER_NAME in (result.stdout or "")


def _docker_recreate_container(compose_file: str = "docker-compose.mssql.yml") -> None:
    """Force-remove the mssql container so the caller can restart it fresh."""
    try:
        subprocess.run(
            ["docker", "rm", "-f", _CONTAINER_NAME],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return


def cleanup_mssql_session(root: Path | None = None) -> None:
    """Remove the Docker container and session files so the next run starts clean.

    Silently ignores errors (best-effort cleanup).
    """
    import shutil

    base = root or find_repo_root()

    subprocess.run(
        ["docker", "rm", "-f", _CONTAINER_NAME],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Preserve .sa_password so the next session reuses the same password
    # that the Docker container was created with.
    mssql_out = base / "output" / "mssql"
    if mssql_out.exists():
        for child in mssql_out.iterdir():
            if child.name == ".sa_password":
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

    mssql_restore = base / "output" / "mssql_restore"
    if mssql_restore.exists():
        shutil.rmtree(mssql_restore, ignore_errors=True)


def probe_sql_server_safe(explicit_url: str | None = None) -> tuple[str | None, Exception | None]:
    """Like probe_sql_server but also returns the last error text on failure."""
    from gis2dgs.input.readers.mssql_backup import probe_status

    status = probe_status(explicit_url)
    if status.url:
        return status.url, None
    if status.error:
        return None, RuntimeError(status.error)
    return None, None


def ensure_sql_server(explicit_url: str | None = None) -> str:
    """
    Return a working master connection URL, probing first and auto-running
    scripts/ensure_mssql.ps1 when no instance is reachable.

    Login failure 18456 or an invalid ODBC attribute on a local Docker sa URL
    recreates gis2dgs-mssql even when probe_sql_server() swallows the error.
    """

    from gis2dgs.input.readers.mssql_backup import (
        MISSING_SERVER_ERROR,
        probe_status,
        sanitize_odbc_url,
        wait_for_docker_odbc,
    )

    prepare_mssql_environment()
    cleaned = sanitize_odbc_url(explicit_url) if explicit_url else None

    status = probe_status(cleaned)
    if status.url:
        os.environ["GIS2DGS_MSSQL_URL"] = status.url
        return status.url

    stale = status.stale_connection or _docker_container_present()
    if stale:
        exit_code = run_ensure_script(quiet=True)
        prepare_mssql_environment()
        waited = wait_for_docker_odbc(timeout_seconds=15)
        if waited.get("ok") and waited.get("url"):
            os.environ["GIS2DGS_MSSQL_URL"] = str(waited["url"])
            return str(waited["url"])
        status = probe_status(cleaned)
        if status.url:
            os.environ["GIS2DGS_MSSQL_URL"] = status.url
            return status.url
        extra = _ENSURE_EXIT_MESSAGES.get(exit_code, "")
        detail = str(waited.get("error") or status.error or "").strip()
        raise InputError(
            "No hay SQL Server accesible por ODBC. "
            f"{extra} {detail}".strip()
        )

    exit_code = run_ensure_script(quiet=True)
    prepare_mssql_environment()
    waited = wait_for_docker_odbc(timeout_seconds=15)
    if waited.get("ok") and waited.get("url"):
        os.environ["GIS2DGS_MSSQL_URL"] = str(waited["url"])
        return str(waited["url"])
    status = probe_status(cleaned)
    if status.url:
        os.environ["GIS2DGS_MSSQL_URL"] = status.url
        return status.url

    extra = _ENSURE_EXIT_MESSAGES.get(exit_code, "")
    detail = (status.error or "").strip()
    if extra:
        raise InputError(
            f"No hay SQL Server accesible para restaurar el .bak. {extra} {detail}".strip()
        )
    raise InputError(MISSING_SERVER_ERROR)


def export_session_env_lines() -> tuple[str, ...]:
    """Return PowerShell lines for the current MSSQL session (for RUN.ps1)."""

    lines: list[str] = []
    for key in _MSSQL_ENV_KEYS:
        value = os.environ.get(key, "").strip()
        if value:
            escaped = value.replace("'", "''")
            lines.append(f"$env:{key} = '{escaped}'")
    return tuple(lines)
