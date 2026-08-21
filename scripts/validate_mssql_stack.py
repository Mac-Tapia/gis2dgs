"""Deep validation of the GIS2DGS SQL Server / ODBC / .bak restore stack.

Run after scripts/ensure_mssql.ps1 (or with GIS2DGS_MSSQL_URL configured):

    python scripts/validate_mssql_stack.py
    python scripts/validate_mssql_stack.py --restore-roundtrip
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis2dgs.input.mssql_ensure import ensure_sql_server, prepare_mssql_environment
from gis2dgs.input.readers.mssql_backup import (
    MssqlBackupReader,
    connection_is_stale,
    connection_is_windows_auth_rejected,
    connection_needs_sql_reconnect,
    decode_odbc_connect,
    docker_master_url,
    has_modern_odbc_driver,
    installed_odbc_drivers,
    probe_report,
    probe_sql_server,
    sql_auth_odbc_connects,
    wait_for_docker_odbc,
)


@dataclass(slots=True)
class Check:
    name: str
    ok: bool
    detail: str = ""


def _run(name: str, fn) -> Check:
    try:
        ok, detail = fn()
        return Check(name=name, ok=bool(ok), detail=str(detail))
    except Exception as exc:
        return Check(name=name, ok=False, detail=f"{type(exc).__name__}: {exc}")


def validate_static() -> list[Check]:
    checks: list[Check] = []

    def drivers_ok():
        names = installed_odbc_drivers()
        return bool(names), list(names)

    checks.append(_run("installed_odbc_drivers", drivers_ok))
    checks.append(
        _run(
            "modern_odbc_present",
            lambda: (has_modern_odbc_driver(), has_modern_odbc_driver()),
        )
    )

    def variant_shape():
        names = installed_odbc_drivers()
        driver = names[0] if names else "SQL Server"
        variants = sql_auth_odbc_connects(
            host="127.0.0.1",
            port="1433",
            user="sa",
            password="TestPass1!",
            drivers=(driver,),
        )
        bad = [v for v in variants if "UID=sa" not in v or "Trusted_Connection" in v]
        return not bad, f"{len(variants)} variant(s)"

    checks.append(_run("sql_auth_variant_shape", variant_shape))

    def error_taxonomy():
        w = Exception("18452 untrusted domain integrated authentication")
        s = Exception("Login failed for user 'sa'. (18456)")
        return (
            connection_needs_sql_reconnect(w)
            and connection_needs_sql_reconnect(s)
            and not connection_is_stale(w)
            and connection_is_windows_auth_rejected(w),
            "18452=reconnect not stale; 18456=reconnect",
        )

    checks.append(_run("error_taxonomy", error_taxonomy))
    return checks


def validate_live(*, require_docker: bool) -> list[Check]:
    checks: list[Check] = []
    prepare_mssql_environment()

    def docker_running():
        try:
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    "name=gis2dgs-mssql",
                    "--filter",
                    "status=running",
                    "--format",
                    "{{.Names}}",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (FileNotFoundError, OSError) as exc:
            return (not require_docker, str(exc))
        running = "gis2dgs-mssql" in (result.stdout or "")
        return (running or not require_docker, (result.stdout or "").strip() or "not running")

    checks.append(_run("docker_container_running", docker_running))

    def session_url():
        url = os.environ.get("GIS2DGS_MSSQL_URL", "").strip()
        if not url:
            rebuilt = docker_master_url()
            return bool(rebuilt), rebuilt or "missing GIS2DGS_MSSQL_URL"
        return True, url[:160]

    checks.append(_run("session_url", session_url))

    def odbc_shape():
        url = os.environ.get("GIS2DGS_MSSQL_URL", "")
        raw = decode_odbc_connect(url)
        if raw is None:
            return False, "expected odbc_connect URL for Docker sa"
        ok = (
            "UID=sa" in raw
            and "Trusted_Connection" not in raw
            and ("Authentication=SqlPassword" in raw or "PWD=" in raw)
        )
        return ok, raw[:200]

    checks.append(_run("odbc_connect_shape", odbc_shape))

    def probe():
        report = probe_report()
        return report.get("ok") is True, report

    checks.append(_run("probe_report", probe))

    def ensure():
        url = ensure_sql_server()
        return bool(url), url[:160]

    checks.append(_run("ensure_sql_server", ensure))

    def wait_odbc():
        waited = wait_for_docker_odbc(timeout_seconds=30)
        return waited.get("ok") is True, waited

    checks.append(_run("wait_for_docker_odbc", wait_odbc))

    def sqlalchemy_ping():
        from sqlalchemy import create_engine, text

        url = probe_sql_server(os.environ.get("GIS2DGS_MSSQL_URL"))
        if not url:
            return False, "probe_sql_server returned None"
        engine = create_engine(url, isolation_level="AUTOCOMMIT", connect_args={"timeout": 8})
        try:
            with engine.connect() as conn:
                version = conn.execute(text("SELECT @@VERSION")).scalar()
            return True, str(version)[:100]
        finally:
            engine.dispose()

    checks.append(_run("sqlalchemy_version", sqlalchemy_ping))
    return checks


def validate_restore_roundtrip() -> list[Check]:
    checks: list[Check] = []
    prepare_mssql_environment()

    roundtrip = ROOT / "scripts" / "mssql_backup_roundtrip.py"
    if not roundtrip.is_file():
        return [Check("roundtrip_script", False, "missing scripts/mssql_backup_roundtrip.py")]

    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, str(roundtrip)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    detail = (result.stdout or result.stderr or "").strip()
    if result.returncode == 0:
        try:
            payload = json.loads(result.stdout)
            ok = payload.get("ok") is True
            checks.append(Check("roundtrip_json", ok, detail[:500]))
        except json.JSONDecodeError:
            checks.append(Check("roundtrip_json", True, detail[:500]))
    else:
        checks.append(Check("roundtrip_exit", False, detail[:500]))

    url = probe_sql_server(os.environ.get("GIS2DGS_MSSQL_URL"))
    backup = ROOT / "output" / "mssql" / "backup" / "gis2dgs_fixture.bak"

    def backup_on_host():
        return backup.is_file(), str(backup)

    checks.append(_run("fixture_bak_on_host", backup_on_host))

    if url and backup.is_file():

        def reader_restore():
            reader = MssqlBackupReader(
                backup,
                source_id="validate",
                server_url=url,
                restore_database="gis2dgs_validate",
                replace=True,
            )
            dataset = reader.read()
            names = set(dataset.tables)
            expected = {"buses", "lines", "loads", "sources"}
            missing = expected - names
            return not missing, f"tables={sorted(names)} missing={sorted(missing)}"

        checks.append(_run("mssql_backup_reader", reader_restore))
    else:
        checks.append(
            Check(
                "mssql_backup_reader",
                False,
                "skipped: no url or backup file",
            )
        )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate GIS2DGS MSSQL stack")
    parser.add_argument(
        "--restore-roundtrip",
        action="store_true",
        help="Also run fixture backup + MssqlBackupReader restore",
    )
    parser.add_argument(
        "--require-docker",
        action="store_true",
        help="Fail if gis2dgs-mssql container is not running",
    )
    args = parser.parse_args()

    report: dict[str, Any] = {"checks": []}
    for check in validate_static():
        report["checks"].append(asdict(check))
    for check in validate_live(require_docker=args.require_docker):
        report["checks"].append(asdict(check))
    if args.restore_roundtrip:
        for check in validate_restore_roundtrip():
            report["checks"].append(asdict(check))

    failed = [c for c in report["checks"] if not c["ok"]]
    report["summary"] = "PASS" if not failed else "FAIL"
    report["failed"] = [c["name"] for c in failed]
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
