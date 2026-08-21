import importlib.util
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.mssql

ROOT = Path(__file__).resolve().parents[2]


def test_live_backup_restore_reads_fixture_tables() -> None:
    url = os.getenv("GIS2DGS_MSSQL_URL")
    if not url:
        pytest.skip(
            "GIS2DGS_MSSQL_URL is not configured. Run scripts/ensure_mssql.ps1 "
            "and export GIS2DGS_MSSQL_URL."
        )

    path = ROOT / "scripts" / "mssql_backup_roundtrip.py"
    spec = importlib.util.spec_from_file_location("mssql_backup_roundtrip", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    os.environ["GIS2DGS_MSSQL_URL"] = url
    module.create_fixture_database(url)
    _disk, host_file = module._server_backup_disk()
    assert host_file.exists()
    dataset = module.restore_and_read(url, host_file)
    names = set(dataset.tables)
    for table in ("buses", "lines", "loads", "sources"):
        assert table in names
        assert not dataset.table(table).frame.empty
