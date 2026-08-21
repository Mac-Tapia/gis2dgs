import os
from pathlib import Path

import pytest

from gis2dgs.dgs import inspect_excel_template
from gis2dgs.input import InputReaderFactory, discover_schema

ROOT = Path(__file__).resolve().parents[2]
REAL_REFERENCE_DIR = ROOT / "data" / "reference" / "real"


def _reference_path(env_name: str, bundled_name: str) -> Path:
    configured = os.getenv(env_name)
    if configured:
        return Path(configured)
    return REAL_REFERENCE_DIR / bundled_name


@pytest.mark.external_reference
def test_real_dgs_reference_when_configured() -> None:
    value = _reference_path("GIS2DGS_DGS_REFERENCE", "SALIDA_DGS.xlsx")
    if not value.exists():
        pytest.skip(f"DGS reference not available: {value}")
    report = inspect_excel_template(value)
    assert report.dgs_format_version == "5"
    by_name = {sheet.sheet: sheet for sheet in report.sheets}
    assert {"General", "ElmNet", "TypLne", "StaCubic", "StaSwitch"}.issubset(by_name)
    assert "bline(r)" in by_name["TypLne"].columns
    assert "obj_bus(i)" in by_name["StaCubic"].columns
    assert "obj_id(p)" in by_name["StaCubic"].columns
    assert "on_off(i)" in by_name["StaSwitch"].columns


@pytest.mark.external_reference
def test_real_input_export_when_configured() -> None:
    value = _reference_path("GIS2DGS_REAL_INPUT", "M_ALIMENTAD.xlsx")
    if not value.exists():
        pytest.skip(f"Real input reference not available: {value}")
    dataset = InputReaderFactory.create(str(value)).read()
    report = discover_schema(dataset)
    assert report.tables
    table = report.tables[0]
    columns = {column.name for column in table.columns}
    expected = {
        "id",
        "id_emp",
        "codset",
        "codali",
        "codigo",
        "id_zona",
        "tension",
        "conexionn",
        "dmax",
        "cosfi",
    }
    assert expected.issubset(columns)
