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
    assert "NetworkID" in tables["NODE"].columns
    assert "NetworkID" in tables["SECTION"].columns


def test_parse_repeated_format_section_keeps_all_feeders(tmp_path: Path) -> None:
    """CYMDIST repeats FORMAT_SECTION once per FEEDER= block; must not overwrite."""

    path = tmp_path / "multi_feeder.txt"
    path.write_text(
        "\n".join(
            [
                "[GENERAL]",
                "CYMDIST_VERSION=4.7",
                "",
                "[HEADNODES]",
                "FORMAT_HEADNODES=NodeID,NetworkID",
                "NODE_A,NET_A",
                "NODE_D,NET_B",
                "",
                "[NODE]",
                "FORMAT_NODE=NodeID,CoordX,CoordY",
                "NODE_A,0,0",
                "NODE_B,1,0",
                "NODE_C,2,0",
                "NODE_D,3,0",
                "NODE_E,4,0",
                "",
                "[SECTION]",
                "FORMAT_FEEDER=NetworkID,HeadNodeID,CoordSet,Year,Description,Color,LoadFactor",
                "FEEDER=NET_A,NODE_A,1,2026,,,1.0",
                "FORMAT_SECTION=SectionID,FromNodeID,ToNodeID,Phase",
                "SEC_AB,NODE_A,NODE_B,ABC",
                "SEC_BC,NODE_B,NODE_C,ABC",
                "FEEDER=NET_B,NODE_D,1,2026,,,1.0",
                "FORMAT_SECTION=SectionID,FromNodeID,ToNodeID,Phase",
                "SEC_DE,NODE_D,NODE_E,ABC",
                "",
                "[LINE CONFIGURATION]",
                "FORMAT_LINECONFIGURATION=SectionID,LineCableID,Length,Overhead",
                "SEC_AB,AA1,10,1",
                "SEC_BC,AA1,20,1",
                "SEC_DE,AA1,30,1",
            ]
        ),
        encoding="utf-8",
    )
    _, tables = parse_cymdist_text(path)
    assert list(tables["SECTION"]["SectionID"]) == ["SEC_AB", "SEC_BC", "SEC_DE"]
    assert list(tables["SECTION"]["NetworkID"]) == ["NET_A", "NET_A", "NET_B"]
    assert "FEEDER" in tables
    assert list(tables["FEEDER"]["NetworkID"]) == ["NET_A", "NET_B"]
    assert "NetworkID" in tables["NODE"].columns
    assert tables["NODE"].set_index("NodeID").loc["NODE_A", "NetworkID"] == "NET_A"
    assert tables["NODE"].set_index("NodeID").loc["NODE_D", "NetworkID"] == "NET_B"


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
    assert assessment.confidence >= 0.9
    assert any(item.role == "equipment_import_config" for item in assessment.files)


def test_assess_tabular_inventory_bundle_uses_role_coverage_not_cymdist(
    tmp_path: Path,
) -> None:
    for name, content in {
        "NMT_IN110.csv": "ID,X,Y\n1,0,0\n",
        "EQPM_IN110.csv": "id0,X1,Y1,X2,Y2\n1,0,0,1,1\n",
        "AMT_IN110.csv": "id,name\n1,feeder\n",
    }.items():
        (tmp_path / name).write_text(content, encoding="utf-8")

    assessment = assess_input_bundle(
        tuple(tmp_path / name for name in ("NMT_IN110.csv", "EQPM_IN110.csv", "AMT_IN110.csv"))
    )

    assert assessment.system_kind == "tabular"
    assert assessment.linked is True
    assert assessment.confidence >= 0.9


def test_assess_single_tabular_file_has_lower_confidence(tmp_path: Path) -> None:
    path = tmp_path / "misc_inventory.csv"
    path.write_text("id,value\n1,2\n", encoding="utf-8")
    assessment = assess_input_bundle((path,))
    assert assessment.confidence < 0.7


def test_enrich_resolves_valuetype_kw_and_pf() -> None:
    import math

    import pandas as pd

    from gis2dgs.input.cymdist_enrich import enrich_cymdist_tables
    from gis2dgs.input.dataset import InputDataset

    dataset = InputDataset()
    dataset.add_table(
        "SECTION",
        pd.DataFrame(
            [{"SectionID": "SEC_AB", "FromNodeID": "NODE_A", "ToNodeID": "NODE_B"}]
        ),
        source_id="red",
    )
    dataset.add_table(
        "CUSTOMER_LOADS",
        pd.DataFrame(
            [
                {
                    "SectionID": "SEC_AB",
                    "DeviceNumber": "DEV_1",
                    "ValueType": 2,
                    "Value1": 50.0,
                    "Value2": 97.0,
                }
            ]
        ),
        source_id="carga",
    )
    enriched = enrich_cymdist_tables(dataset)
    frame = enriched.tables["CUSTOMER_LOADS"].frame
    assert frame.loc[0, "ToNodeID"] == "NODE_B"
    assert abs(float(frame.loc[0, "ActivePower_kW"]) - 50.0) < 1e-6
    expected_q = 50.0 * math.tan(math.acos(0.97))
    assert abs(float(frame.loc[0, "ReactivePower_kvar"]) - expected_q) < 1e-3

