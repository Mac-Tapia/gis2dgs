from pathlib import Path

import pytest

from gis2dgs.input import InputKind, assess_input_bundle, detect_input_kind
from gis2dgs.input.readers.cymdist_text import (
    CymdistTextInputReader,
    is_cymdist_import_config,
    is_cymdist_network_export,
    parse_cymdist_text,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "cymdist"


def test_detect_cymdist_text_kind() -> None:
    red = FIXTURES / "RED_030826_SAMPLE.txt"
    assert detect_input_kind(red) is InputKind.CYMDIST_TEXT
    assert is_cymdist_network_export(red)


def test_import_config_is_recognized_but_not_data() -> None:
    config = FIXTURES / "BD_Equipo_V26.txt"
    assert is_cymdist_import_config(config)
    with pytest.raises(Exception):
        CymdistTextInputReader(config).read()


def test_parse_red_sections_and_enrich_length() -> None:
    _, tables = parse_cymdist_text(FIXTURES / "RED_030826_SAMPLE.txt")
    assert "NODE" in tables
    assert "SECTION" in tables
    assert "Length" in tables["SECTION"].columns
    assert tables["SECTION"].loc[0, "SectionID"] == "SEC_AB"


def test_assess_linked_cymdist_bundle() -> None:
    assessment = assess_input_bundle(
        (
            FIXTURES / "RED_030826_SAMPLE.txt",
            FIXTURES / "CARGA_030826_SAMPLE.txt",
            FIXTURES / "BD_Equipo_V26.txt",
        )
    )
    assert assessment.linked is True
    assert assessment.system_kind == "distribution"
    assert assessment.cross_reference_ratio == 1.0
    assert any(item.role == "equipment_import_config" for item in assessment.files)
