from pathlib import Path

import pytest

from gis2dgs.input.exceptions import InputError
from gis2dgs.input.mssql_ensure import (
    _CONTAINER_NAME,
    _docker_recreate_container,
    _is_login_failed,
    apply_session_env,
    ensure_sql_server,
    find_repo_root,
    prepare_mssql_environment,
    run_ensure_script,
    session_env_path,
)
from gis2dgs.input.readers.mssql_backup import ProbeStatus


def test_find_repo_root_points_to_scripts() -> None:
    root = find_repo_root()
    assert (root / "scripts" / "ensure_mssql.ps1").is_file()


def test_apply_session_env_loads_variables(tmp_path: Path) -> None:
    session = tmp_path / "session.env.ps1"
    session.write_text(
        "$env:GIS2DGS_MSSQL_URL = 'mssql+pyodbc://localhost/master'\n"
        "$env:GIS2DGS_MSSQL_HOST_STAGE_DIR = 'C:\\stage'\n",
        encoding="utf-8",
    )
    apply_session_env(session)
    assert "localhost" in __import__("os").environ["GIS2DGS_MSSQL_URL"]
    assert __import__("os").environ["GIS2DGS_MSSQL_HOST_STAGE_DIR"] == "C:\\stage"


def test_prepare_rebuilds_local_sa_url_from_password_file(tmp_path: Path, monkeypatch) -> None:
    import os

    mssql_dir = tmp_path / "output" / "mssql"
    mssql_dir.mkdir(parents=True)
    (mssql_dir / ".sa_password").write_text("Gis2dgs_Test1!", encoding="utf-8")
    session = mssql_dir / "session.env.ps1"
    session.write_text(
        "$env:GIS2DGS_MSSQL_URL = "
        "'mssql+pyodbc://sa:StalePass@127.0.0.1:1433/master"
        "?driver=SQL+Server&TrustServerCertificate=yes'\n"
        "$env:GIS2DGS_MSSQL_DOCKER = 'true'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("gis2dgs.input.mssql_ensure.find_repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.installed_odbc_drivers",
        lambda: ("ODBC Driver 17 for SQL Server",),
    )
    monkeypatch.setenv("GIS2DGS_MSSQL_HOST", "127.0.0.1")
    monkeypatch.setenv("GIS2DGS_MSSQL_PORT", "1433")
    prepare_mssql_environment(session)
    url = os.environ["GIS2DGS_MSSQL_URL"]
    from urllib.parse import unquote_plus

    raw = unquote_plus(url.split("odbc_connect=", 1)[-1]) if "odbc_connect=" in url else url
    assert "StalePass" not in url
    assert "TrustServerCertificate=yes" in raw
    assert "ODBC Driver 17" in raw
    assert "Gis2dgs_Test1" in raw
    assert "Authentication=SqlPassword" in raw


def test_ensure_sql_server_returns_probe_without_script(monkeypatch) -> None:
    monkeypatch.setattr(
        "gis2dgs.input.mssql_ensure.prepare_mssql_environment",
        lambda path=None: False,
    )
    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.probe_status",
        lambda explicit_url=None: ProbeStatus("mssql+pyodbc://localhost/master"),
    )
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        return 0

    monkeypatch.setattr("gis2dgs.input.mssql_ensure.run_ensure_script", fake_run)
    url = ensure_sql_server()
    assert "localhost" in url
    assert not called


def test_ensure_sql_server_invokes_script_when_probe_fails(monkeypatch) -> None:
    probes = [
        ProbeStatus(None),
        ProbeStatus("mssql+pyodbc://127.0.0.1:1433/master"),
    ]

    def fake_probe(explicit_url=None):
        return probes.pop(0) if probes else ProbeStatus(None)

    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.probe_status",
        fake_probe,
    )
    monkeypatch.setattr(
        "gis2dgs.input.mssql_ensure.prepare_mssql_environment",
        lambda path=None: False,
    )
    monkeypatch.setattr(
        "gis2dgs.input.mssql_ensure._docker_container_present",
        lambda: False,
    )
    calls: list[bool] = []

    def fake_run(*args, **kwargs):
        calls.append(kwargs.get("quiet", False))
        return 0

    monkeypatch.setattr("gis2dgs.input.mssql_ensure.run_ensure_script", fake_run)
    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.wait_for_docker_odbc",
        lambda timeout_seconds=120: {"ok": False, "url": None, "error": None},
    )
    url = ensure_sql_server()
    assert "127.0.0.1" in url
    assert calls == [True]


def test_ensure_sql_server_maps_docker_not_running(monkeypatch) -> None:
    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.probe_status",
        lambda explicit_url=None: ProbeStatus(None),
    )
    monkeypatch.setattr("gis2dgs.input.mssql_ensure.run_ensure_script", lambda **kwargs: 3)
    monkeypatch.setattr(
        "gis2dgs.input.mssql_ensure.prepare_mssql_environment",
        lambda path=None: False,
    )
    monkeypatch.setattr(
        "gis2dgs.input.mssql_ensure._docker_container_present",
        lambda: False,
    )
    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.wait_for_docker_odbc",
        lambda timeout_seconds=120: {"ok": False, "url": None, "error": None},
    )
    with pytest.raises(InputError, match="Docker Desktop"):
        ensure_sql_server()


def test_run_ensure_script_quiet_flag(monkeypatch, tmp_path: Path) -> None:
    root = find_repo_root()
    captured: list[list[str]] = []

    def fake_run(args, **kwargs):
        captured.append(list(args))
        return __import__("subprocess").CompletedProcess(args, 0)

    monkeypatch.setattr("gis2dgs.input.mssql_ensure.subprocess.run", fake_run)
    monkeypatch.setattr("gis2dgs.input.mssql_ensure.find_repo_root", lambda: root)
    monkeypatch.setattr(
        "gis2dgs.input.mssql_ensure.prepare_mssql_environment",
        lambda path=None: False,
    )
    run_ensure_script(quiet=True)
    assert "-Quiet" in captured[0]


def test_session_env_path_under_output() -> None:
    path = session_env_path()
    assert path.name == "session.env.ps1"
    assert path.parent.name == "mssql"


def test_is_login_failed_detects_error_code() -> None:
    assert _is_login_failed(Exception("Login failed for user 'sa'. (18456)"))
    assert _is_login_failed(Exception("18456"))
    assert _is_login_failed(Exception("Atributo de cadena de conexión no válido"))
    assert not _is_login_failed(
        Exception("Login is from an untrusted domain (18452)")
    )
    assert not _is_login_failed(Exception("Connection timeout"))


def test_docker_recreate_container_calls_docker_rm(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return __import__("subprocess").CompletedProcess(args, 0)

    monkeypatch.setattr("gis2dgs.input.mssql_ensure.subprocess.run", fake_run)
    _docker_recreate_container()
    assert calls, "subprocess.run not called"
    assert "rm" in calls[0]
    assert _CONTAINER_NAME in calls[0]


def test_ensure_sql_server_recreates_docker_on_login_failed(monkeypatch) -> None:
    """Recreate gis2dgs-mssql when probe reports 18456 without raising."""

    probe_calls: list[int] = []

    def fake_status(explicit_url=None):
        probe_calls.append(1)
        if len(probe_calls) == 1:
            return ProbeStatus(None, stale_connection=True, error="18456")
        return ProbeStatus("mssql+pyodbc://127.0.0.1:1433/master")

    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.probe_status",
        fake_status,
    )
    monkeypatch.setattr(
        "gis2dgs.input.mssql_ensure.prepare_mssql_environment",
        lambda path=None: False,
    )

    script_calls: list[bool] = []

    def fake_run_ensure(**kwargs):
        script_calls.append(True)
        return 0

    monkeypatch.setattr("gis2dgs.input.mssql_ensure.run_ensure_script", fake_run_ensure)
    monkeypatch.setattr(
        "gis2dgs.input.readers.mssql_backup.wait_for_docker_odbc",
        lambda timeout_seconds=120: {"ok": False, "url": None, "error": None},
    )

    url = ensure_sql_server()
    assert "127.0.0.1" in url
    assert script_calls, "El provisionador no fue invocado tras el error 18456"
