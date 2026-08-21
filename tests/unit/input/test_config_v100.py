from pathlib import Path

from gis2dgs.config.input import InputSourceConfig


def test_input_uri_expands_environment_variables(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIS2DGS_DB_URL", "postgresql+psycopg://user:secret@host/db")
    config = InputSourceConfig(id="db", uri="$GIS2DGS_DB_URL")
    assert config.resolved_uri(tmp_path).startswith("postgresql+psycopg://")
